from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth import login, logout
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib import messages
from django.conf import settings
from django.db.models import Count, Q, Sum
from django.http import JsonResponse, HttpResponse
from django.utils import timezone
from datetime import timedelta
import subprocess
import os

from .forms import RegisterForm
from .models import Workspace, WorkspaceMembership, Product, DatabaseBackup, ActivityLog
from .utils import (
    create_tenant_database,
    delete_tenant_database,
    backup_tenant_database,
    get_database_size,
    check_postgres_connection
)
import logging

logger = logging.getLogger(__name__)


def register(request):
    """Vista de registro de nuevo usuario y workspace"""
    if request.method == 'POST':
        form = RegisterForm(request.POST)
        if form.is_valid():
            try:
                # 1. Crear usuario
                user = form.save(commit=False)
                user.email = form.cleaned_data['email']
                user.first_name = form.cleaned_data['first_name']
                user.save()
                
                # 2. Obtener datos del formulario
                product = form.cleaned_data['product']
                company_name = form.cleaned_data['company_name']
                subdomain = form.get_subdomain()
                
                # 3. Crear base de datos del tenant
                logger.info(f"Creando BD para tenant: {subdomain}")
                db_credentials = create_tenant_database(
                    product.name,
                    subdomain,
                    company_name
                )
                
                # 4. Crear workspace
                workspace = Workspace.objects.create(
                    product=product,
                    company_name=company_name,
                    subdomain=subdomain,
                    db_name=db_credentials['db_name'],
                    db_user=db_credentials['db_user'],
                    db_password=db_credentials['db_password'],
                    db_created=True,
                )
                
                # 5. Asignar usuario como owner
                WorkspaceMembership.objects.create(
                    user=user,
                    workspace=workspace,
                    role='owner'
                )
                
                # 6. Log de actividad
                ActivityLog.objects.create(
                    user=user,
                    workspace=workspace,
                    action='create',
                    description=f'Workspace creado: {workspace.company_name}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                # 7. Login automático
                login(request, user)
                
                messages.success(
                    request,
                    f'¡Bienvenido! Tu espacio de trabajo está listo.'
                )
                
                return redirect('workspace_ready', workspace_id=workspace.id)
                
            except Exception as e:
                logger.error(f"Error al crear workspace: {e}")
                messages.error(request, f"Error al crear el espacio de trabajo: {str(e)}")
                if 'user' in locals() and user.pk:
                    user.delete()
    else:
        form = RegisterForm()
    
    return render(request, 'accounts/register.html', {
        'form': form,
        'domain': settings.TENANT_DOMAIN
    })


@login_required
def dashboard(request):
    """Panel de control - lista de workspaces del usuario"""
    memberships = WorkspaceMembership.objects.filter(
        user=request.user,
        is_active=True
    ).select_related('workspace', 'workspace__product')
    
    return render(request, 'accounts/dashboard.html', {
        'memberships': memberships
    })


@login_required
def workspace_ready(request, workspace_id):
    """Página de confirmación de workspace creado"""
    try:
        membership = WorkspaceMembership.objects.select_related(
            'workspace', 'workspace__product'
        ).get(
            workspace_id=workspace_id,
            user=request.user
        )
        workspace = membership.workspace
        
        return render(request, 'accounts/workspace_ready.html', {
            'workspace': workspace
        })
    except WorkspaceMembership.DoesNotExist:
        messages.error(request, 'No tienes acceso a este workspace')
        return redirect('dashboard')


def user_logout(request):
    """Cerrar sesión"""
    logout(request)
    messages.success(request, 'Has cerrado sesión exitosamente')
    return redirect('login')


# ============================================================================
# PANEL ADMINISTRATIVO
# ============================================================================

def is_staff_user(user):
    """Verificar si el usuario es staff"""
    return user.is_staff or user.is_superuser


@login_required
@user_passes_test(is_staff_user)
def admin_dashboard(request):
    """Dashboard administrativo principal"""
    
    # Filtros
    product_filter = request.GET.get('product', '')
    plan_filter = request.GET.get('plan', '')
    status_filter = request.GET.get('status', '')
    search = request.GET.get('search', '')
    
    # Query base
    workspaces = Workspace.objects.select_related('product').prefetch_related('memberships')
    
    # Aplicar filtros
    if product_filter:
        workspaces = workspaces.filter(product__name=product_filter)
    if plan_filter:
        workspaces = workspaces.filter(plan_type=plan_filter)
    if status_filter:
        workspaces = workspaces.filter(status=status_filter)
    if search:
        workspaces = workspaces.filter(
            Q(company_name__icontains=search) |
            Q(subdomain__icontains=search) |
            Q(db_name__icontains=search)
        )
    
    # Estadísticas
    total_workspaces = Workspace.objects.count()
    active_workspaces = Workspace.objects.filter(status='active').count()
    paused_workspaces = Workspace.objects.filter(status='paused').count()
    total_db_size = Workspace.objects.aggregate(Sum('db_size_mb'))['db_size_mb__sum'] or 0
    
    # Workspaces por producto
    workspaces_by_product = Product.objects.annotate(
        workspace_count=Count('workspaces')
    ).values('name', 'display_name', 'workspace_count', 'icon')
    
    # Workspaces por plan
    workspaces_by_plan = Workspace.objects.values('plan_type').annotate(
        count=Count('id')
    ).order_by('plan_type')
    
    # Próximos a expirar
    expiring_soon = Workspace.objects.filter(
        subscription_end__lte=timezone.now() + timedelta(days=30),
        subscription_end__gt=timezone.now(),
        status='active'
    ).order_by('subscription_end')[:10]
    
    # Actividad reciente
    recent_activity = ActivityLog.objects.select_related(
        'user', 'workspace'
    ).order_by('-created_at')[:20]
    
    context = {
        'workspaces': workspaces,
        'products': Product.objects.all(),
        'total_workspaces': total_workspaces,
        'active_workspaces': active_workspaces,
        'paused_workspaces': paused_workspaces,
        'total_db_size': round(total_db_size, 2),
        'workspaces_by_product': workspaces_by_product,
        'workspaces_by_plan': workspaces_by_plan,
        'expiring_soon': expiring_soon,
        'recent_activity': recent_activity,
        # Filtros actuales
        'current_product': product_filter,
        'current_plan': plan_filter,
        'current_status': status_filter,
        'current_search': search,
    }
    
    return render(request, 'accounts/admin/dashboard.html', context)


@login_required
@user_passes_test(is_staff_user)
def admin_workspace_detail(request, workspace_id):
    """Detalle administrativo de un workspace"""
    workspace = get_object_or_404(
        Workspace.objects.select_related('product').prefetch_related('memberships', 'backups'),
        id=workspace_id
    )
    
    # Actualizar tamaño de BD
    try:
        workspace.db_size_mb = get_database_size(workspace.db_name)
        workspace.save(update_fields=['db_size_mb'])
    except Exception as e:
        logger.error(f"Error obteniendo tamaño de BD: {e}")
    
    # Actividad del workspace
    activity = ActivityLog.objects.filter(
        workspace=workspace
    ).select_related('user').order_by('-created_at')[:50]
    
    context = {
        'workspace': workspace,
        'activity': activity,
    }
    
    return render(request, 'accounts/admin/workspace_detail.html', context)


@login_required
@user_passes_test(is_staff_user)
def admin_workspace_action(request, workspace_id, action):
    """Acciones administrativas sobre workspaces"""
    workspace = get_object_or_404(Workspace, id=workspace_id)
    
    try:
        if action == 'pause':
            workspace.pause()
            ActivityLog.objects.create(
                user=request.user,
                workspace=workspace,
                action='pause',
                description=f'Workspace pausado: {workspace.company_name}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, f'Workspace "{workspace.company_name}" pausado exitosamente')
        
        elif action == 'resume':
            workspace.resume()
            ActivityLog.objects.create(
                user=request.user,
                workspace=workspace,
                action='resume',
                description=f'Workspace reactivado: {workspace.company_name}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.success(request, f'Workspace "{workspace.company_name}" reactivado exitosamente')
        
        elif action == 'suspend':
            workspace.status = 'suspended'
            workspace.save()
            ActivityLog.objects.create(
                user=request.user,
                workspace=workspace,
                action='update',
                description=f'Workspace suspendido: {workspace.company_name}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            messages.warning(request, f'Workspace "{workspace.company_name}" suspendido')
        
        elif action == 'delete':
            company_name = workspace.company_name
            db_name = workspace.db_name
            
            # Eliminar base de datos
            try:
                delete_tenant_database(db_name)
            except Exception as e:
                logger.error(f"Error eliminando BD: {e}")
            
            # Log antes de eliminar
            ActivityLog.objects.create(
                user=request.user,
                workspace=None,
                action='delete',
                description=f'Workspace eliminado: {company_name}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            # Eliminar workspace
            workspace.delete()
            messages.success(request, f'Workspace "{company_name}" eliminado exitosamente')
            return redirect('admin_dashboard')
        
        elif action == 'backup':
            try:
                backup_path = backup_tenant_database(workspace.db_name)
                
                # Crear registro de backup
                DatabaseBackup.objects.create(
                    workspace=workspace,
                    filename=os.path.basename(backup_path),
                    file_path=backup_path,
                    backup_type='manual',
                    created_by=request.user,
                    notes=f'Backup manual creado por {request.user.username}'
                )
                
                ActivityLog.objects.create(
                    user=request.user,
                    workspace=workspace,
                    action='backup',
                    description=f'Backup creado para: {workspace.company_name}',
                    ip_address=request.META.get('REMOTE_ADDR')
                )
                
                messages.success(request, f'Backup creado exitosamente')
            except Exception as e:
                messages.error(request, f'Error al crear backup: {str(e)}')
        
        elif action == 'sync_size':
            try:
                workspace.db_size_mb = get_database_size(workspace.db_name)
                workspace.save(update_fields=['db_size_mb'])
                messages.success(request, f'Tamaño de BD actualizado: {workspace.db_size_mb:.2f} MB')
            except Exception as e:
                messages.error(request, f'Error al obtener tamaño: {str(e)}')
        
    except Exception as e:
        logger.error(f"Error en acción {action}: {e}")
        messages.error(request, f'Error al ejecutar la acción: {str(e)}')
    
    return redirect('admin_workspace_detail', workspace_id=workspace_id)


@login_required
@user_passes_test(is_staff_user)
def admin_database_manager(request):
    """Gestor de bases de datos"""
    workspaces = Workspace.objects.select_related('product').all()
    
    # Verificar conexión a PostgreSQL
    pg_status = check_postgres_connection()
    
    # Listar todas las bases de datos
    db_list = []
    for workspace in workspaces:
        db_list.append({
            'workspace': workspace,
            'size': workspace.db_size_mb,
            'created': workspace.db_created,
        })
    
    context = {
        'workspaces': workspaces,
        'db_list': db_list,
        'pg_status': pg_status,
    }
    
    return render(request, 'accounts/admin/database_manager.html', context)


@login_required
@user_passes_test(is_staff_user)
def admin_activity_log(request):
    """Registro de actividades"""
    activities = ActivityLog.objects.select_related(
        'user', 'workspace'
    ).order_by('-created_at')
    
    # Filtros
    action_filter = request.GET.get('action', '')
    user_filter = request.GET.get('user', '')
    
    if action_filter:
        activities = activities.filter(action=action_filter)
    if user_filter:
        activities = activities.filter(user__username__icontains=user_filter)
    
    context = {
        'activities': activities[:200],  # Últimas 200
        'current_action': action_filter,
        'current_user': user_filter,
    }
    
    return render(request, 'accounts/admin/activity_log.html', context)


@login_required
@user_passes_test(is_staff_user)
def admin_products(request):
    """Gestión de productos"""
    products = Product.objects.annotate(
        workspace_count=Count('workspaces')
    ).order_by('name')
    
    context = {
        'products': products,
    }
    
    return render(request, 'accounts/admin/products.html', context)
