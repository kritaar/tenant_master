"""
Vistas para el panel de administración de Tenant Master
"""
from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.db.models import Count, Sum
from .models import Workspace, Product, WorkspaceMembership, ActivityLog, PlanChange
import logging

logger = logging.getLogger(__name__)


def is_staff_user(user):
    """Verificar si el usuario es staff"""
    return user.is_staff or user.is_superuser


def index(request):
    """Página de inicio"""
    if request.user.is_authenticated:
        if request.user.is_staff:
            return redirect('admin_dashboard')
        return redirect('dashboard')
    return redirect('login')


@login_required
def dashboard(request):
    """Dashboard de usuario normal"""
    memberships = WorkspaceMembership.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('workspace', 'workspace__product')
    
    return render(request, 'accounts/dashboard.html', {
        'memberships': memberships
    })


def user_logout(request):
    """Cerrar sesión"""
    logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente')
    return redirect('login')


# ============================================================================
# PANEL ADMINISTRATIVO
# ============================================================================

@login_required
@user_passes_test(is_staff_user)
def admin_dashboard(request):
    """Dashboard administrativo - Resumen"""
    
    # Estadísticas generales
    total_workspaces = Workspace.objects.count()
    active_workspaces = Workspace.objects.filter(status='active').count()
    total_clients = WorkspaceMembership.objects.values('user').distinct().count()
    
    # Workspaces por producto
    workspaces_by_product = Product.objects.annotate(
        workspace_count=Count('workspaces')
    ).values('name', 'display_name', 'workspace_count', 'icon')
    
    # Deployment types
    shared_count = Workspace.objects.filter(deployment_type='shared').count()
    dedicated_count = Workspace.objects.filter(deployment_type='dedicated').count()
    
    # Bases de datos
    total_db_size = Workspace.objects.aggregate(Sum('db_size_mb'))['db_size_mb__sum'] or 0
    total_databases = Workspace.objects.filter(db_created=True).count()
    
    context = {
        'total_workspaces': total_workspaces,
        'active_workspaces': active_workspaces,
        'total_clients': total_clients,
        'shared_count': shared_count,
        'dedicated_count': dedicated_count,
        'total_databases': total_databases,
        'total_db_size': round(total_db_size, 2),
        'workspaces_by_product': workspaces_by_product,
    }
    
    return render(request, 'accounts/admin/dashboard.html', context)


@login_required
@user_passes_test(is_staff_user)
def admin_workspaces(request):
    """Lista de workspaces"""
    
    # Filtros
    product_filter = request.GET.get('product', '')
    plan_filter = request.GET.get('plan', '')
    deployment_filter = request.GET.get('deployment', '')
    search = request.GET.get('search', '')
    
    workspaces = Workspace.objects.select_related('product').all()
    
    if product_filter:
        workspaces = workspaces.filter(product__name=product_filter)
    if plan_filter:
        workspaces = workspaces.filter(plan_type=plan_filter)
    if deployment_filter:
        workspaces = workspaces.filter(deployment_type=deployment_filter)
    if search:
        workspaces = workspaces.filter(company_name__icontains=search)
    
    products = Product.objects.filter(is_active=True)
    
    context = {
        'workspaces': workspaces,
        'products': products,
        'current_product': product_filter,
        'current_plan': plan_filter,
        'current_deployment': deployment_filter,
        'current_search': search,
    }
    
    return render(request, 'accounts/admin/workspaces.html', context)


@login_required
@user_passes_test(is_staff_user)
def admin_workspace_detail(request, workspace_id):
    """Detalle de un workspace"""
    workspace = get_object_or_404(
        Workspace.objects.select_related('product'),
        id=workspace_id
    )
    
    # Actividad reciente
    activity = ActivityLog.objects.filter(
        workspace=workspace
    ).select_related('user').order_by('-created_at')[:20]
    
    # Historial de cambios de plan
    plan_changes = PlanChange.objects.filter(
        workspace=workspace
    ).select_related('changed_by').order_by('-created_at')[:10]
    
    context = {
        'workspace': workspace,
        'activity': activity,
        'plan_changes': plan_changes,
    }
    
    return render(request, 'accounts/admin/workspace_detail.html', context)


@login_required
@user_passes_test(is_staff_user)
def admin_create_workspace(request):
    """Crear nuevo workspace"""
    if request.method == 'POST':
        try:
            company_name = request.POST.get('company_name')
            product_id = request.POST.get('product')
            subdomain = request.POST.get('subdomain')
            plan_type = request.POST.get('plan_type', 'free')
            
            product = Product.objects.get(id=product_id)
            
            # Determinar tipo de deployment según el plan
            deployment_type = 'dedicated' if plan_type in ['enterprise', 'lifetime'] else 'shared'
            
            # Por ahora, solo crear el workspace sin base de datos real
            # La creación de BD la implementaremos después
            workspace = Workspace.objects.create(
                product=product,
                company_name=company_name,
                subdomain=subdomain,
                plan_type=plan_type,
                deployment_type=deployment_type,
                container_name=product.shared_container_name,
                container_port=product.shared_container_port,
                db_name=f"{product.name}_{subdomain}",
                db_user=f"user_{product.name}_{subdomain}",
                db_password="changeme123",  # Temporal
                status='active',
            )
            
            # Log
            ActivityLog.objects.create(
                user=request.user,
                workspace=workspace,
                action='create',
                description=f'Workspace creado: {workspace.company_name} ({deployment_type})',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(
                request,
                f'✅ Workspace "{workspace.company_name}" creado exitosamente'
            )
            
            return redirect('admin_workspace_detail', workspace_id=workspace.id)
            
        except Exception as e:
            logger.error(f"Error creando workspace: {e}")
            messages.error(request, f'Error: {str(e)}')
    
    products = Product.objects.filter(is_active=True)
    return render(request, 'accounts/admin/create_workspace.html', {
        'products': products
    })


@login_required
@user_passes_test(is_staff_user)
def admin_change_plan(request, workspace_id):
    """Cambiar plan de un workspace"""
    workspace = get_object_or_404(Workspace, id=workspace_id)
    
    if request.method == 'POST':
        new_plan = request.POST.get('new_plan')
        reason = request.POST.get('reason', '')
        
        if new_plan == workspace.plan_type:
            messages.warning(request, 'El workspace ya tiene ese plan')
            return redirect('admin_workspace_detail', workspace_id)
        
        try:
            old_plan = workspace.plan_type
            old_deployment = workspace.deployment_type
            
            # Actualizar plan
            workspace.previous_plan = old_plan
            workspace.plan_type = new_plan
            workspace.plan_changed_by = request.user
            
            # Determinar si necesita cambiar deployment
            if new_plan in ['enterprise', 'lifetime']:
                workspace.deployment_type = 'dedicated'
            else:
                workspace.deployment_type = 'shared'
            
            workspace.save()
            
            # Registrar cambio
            PlanChange.objects.create(
                workspace=workspace,
                changed_by=request.user,
                old_plan=old_plan,
                new_plan=new_plan,
                old_deployment=old_deployment,
                new_deployment=workspace.deployment_type,
                migration_required=old_deployment != workspace.deployment_type,
                reason=reason
            )
            
            # Log
            ActivityLog.objects.create(
                user=request.user,
                workspace=workspace,
                action='plan_change',
                description=f'Plan cambiado: {old_plan} → {new_plan}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(request, f'✅ Plan actualizado a {new_plan}')
            
        except Exception as e:
            logger.error(f"Error cambiando plan: {e}")
            messages.error(request, f'Error: {str(e)}')
    
    return redirect('admin_workspace_detail', workspace_id)


@login_required
@user_passes_test(is_staff_user)
def admin_workspace_action(request, workspace_id, action):
    """Acciones sobre workspaces"""
    workspace = get_object_or_404(Workspace, id=workspace_id)
    
    try:
        if action == 'pause':
            workspace.pause()
            messages.success(request, f'Workspace pausado')
        
        elif action == 'resume':
            workspace.resume()
            messages.success(request, f'Workspace reactivado')
        
        elif action == 'delete':
            company_name = workspace.company_name
            workspace.delete()
            messages.success(request, f'Workspace "{company_name}" eliminado')
            return redirect('admin_workspaces')
        
        # Log
        ActivityLog.objects.create(
            user=request.user,
            workspace=workspace if action != 'delete' else None,
            action=action,
            description=f'Acción: {action} en {company_name if action == "delete" else workspace.company_name}',
            ip_address=request.META.get('REMOTE_ADDR')
        )
        
    except Exception as e:
        logger.error(f"Error en acción {action}: {e}")
        messages.error(request, f'Error: {str(e)}')
    
    return redirect('admin_workspace_detail', workspace_id) if action != 'delete' else redirect('admin_workspaces')


@login_required
@user_passes_test(is_staff_user)
def admin_clients(request):
    """Lista de clientes"""
    memberships = WorkspaceMembership.objects.select_related(
        'user', 'workspace', 'workspace__product'
    ).all()
    
    return render(request, 'accounts/admin/clients.html', {
        'memberships': memberships
    })


@login_required
@user_passes_test(is_staff_user)
def admin_deployments(request):
    """Gestión de deployments"""
    products = Product.objects.annotate(
        workspace_count=Count('workspaces')
    ).all()
    
    return render(request, 'accounts/admin/deployments.html', {
        'products': products
    })


@login_required
@user_passes_test(is_staff_user)
def admin_products(request):
    """Gestión de productos"""
    products = Product.objects.annotate(
        workspace_count=Count('workspaces')
    ).all()
    
    return render(request, 'accounts/admin/products.html', {
        'products': products
    })


@login_required
@user_passes_test(is_staff_user)
def admin_migrations(request):
    """Historial de migraciones"""
    plan_changes = PlanChange.objects.select_related(
        'workspace', 'changed_by'
    ).order_by('-created_at')[:50]
    
    return render(request, 'accounts/admin/migrations.html', {
        'plan_changes': plan_changes
    })


@login_required
@user_passes_test(is_staff_user)
def admin_databases(request):
    """Gestión de bases de datos"""
    workspaces = Workspace.objects.select_related('product').all()
    
    return render(request, 'accounts/admin/databases.html', {
        'workspaces': workspaces
    })


@login_required
@user_passes_test(is_staff_user)
def admin_settings(request):
    """Configuración del sistema"""
    return render(request, 'accounts/admin/settings.html', {})
