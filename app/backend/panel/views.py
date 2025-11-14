"""
Views del Panel de Administración Tenant Master
Versión funcional SIN modelo Deployment
"""

from django.shortcuts import render, redirect, get_object_or_404
from django.contrib.auth.decorators import login_required, user_passes_test
from django.contrib.auth import logout
from django.contrib import messages
from django.http import JsonResponse, HttpResponse
from django.conf import settings
from django.db.models import Count, Q
from .models import Tenant, Product, TenantUser, ActivityLog
from django.contrib.auth.models import User
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import secrets
import string


def is_superuser(user):
    return user.is_superuser


def generate_password(length=32):
    """Genera contraseña segura"""
    alphabet = string.ascii_letters + string.digits
    return ''.join(secrets.choice(alphabet) for _ in range(length))


def index(request):
    if request.user.is_authenticated:
        return redirect('panel_dashboard')
    return redirect('login')


def user_logout(request):
    logout(request)
    return redirect('login')


def health_check(request):
    return HttpResponse("OK", status=200)


@login_required
@user_passes_test(is_superuser)
def dashboard(request):
    """Dashboard principal"""
    try:
        total_tenants = Tenant.objects.count()
        active_tenants = Tenant.objects.filter(status='active').count()
        
        # Contar por tipo
        dedicated_count = Tenant.objects.filter(type='dedicated').count()
        shared_count = Tenant.objects.filter(type='shared').count()
        
        recent_tenants = Tenant.objects.select_related('product', 'owner').order_by('-created_at')[:10]
        recent_activity = ActivityLog.objects.select_related('user', 'tenant').order_by('-created_at')[:10]
        
        context = {
            'total_tenants': total_tenants,
            'active_tenants': active_tenants,
            'dedicated_count': dedicated_count,
            'shared_count': shared_count,
            'recent_tenants': recent_tenants,
            'recent_activity': recent_activity,
        }
        return render(request, 'panel/dashboard.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar dashboard: {str(e)}')
        return render(request, 'panel/dashboard.html', {'error': str(e)})


@login_required
@user_passes_test(is_superuser)
def workspaces(request):
    """Lista de workspaces"""
    try:
        tenants = Tenant.objects.select_related('product', 'owner').all()
        products = Product.objects.filter(is_active=True)
        
        context = {
            'tenants': tenants,
            'products': products,
        }
        return render(request, 'panel/workspaces.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar workspaces: {str(e)}')
        return render(request, 'panel/workspaces.html', {'tenants': [], 'products': []})


@login_required
@user_passes_test(is_superuser)
def create_workspace(request):
    """Crea un nuevo workspace"""
    if request.method == 'POST':
        try:
            # 1. Recoger datos del formulario
            company_name = request.POST.get('company_name')
            subdomain = request.POST.get('subdomain').lower()
            product_id = request.POST.get('product')
            plan = request.POST.get('plan', 'free')
            workspace_type = request.POST.get('type', 'dedicated')
            owner_username = request.POST.get('owner_username')
            
            # 2. Validaciones
            if Tenant.objects.filter(subdomain=subdomain).exists():
                messages.error(request, f'El subdominio {subdomain} ya existe')
                return redirect('create_workspace')
            
            product = Product.objects.get(id=product_id)
            owner = User.objects.get(username=owner_username)
            
            # 3. Generar credenciales de BD
            db_name = f"tenant_{subdomain}"
            db_user = f"user_{subdomain}"
            db_password = generate_password()
            
            # 4. Crear base de datos
            create_database(db_name, db_user, db_password)
            
            # 5. Definir paths según el tipo
            if workspace_type == 'dedicated':
                project_path = f"/var/deployments/{product.name.lower()}-{subdomain}"
                stack_path = f"/var/deployments/{product.name.lower()}-{subdomain}/docker-compose.yml"
            else:  # shared
                project_path = product.template_path or f"/opt/proyectos/{product.name.lower()}"
                stack_path = ""
            
            # 6. Crear tenant
            tenant = Tenant.objects.create(
                name=company_name,
                subdomain=subdomain,
                company_name=company_name,
                product=product,
                plan=plan,
                type=workspace_type,
                status='active',
                db_name=db_name,
                db_user=db_user,
                db_password=db_password,
                project_path=project_path,
                stack_path=stack_path,
                owner=owner,
                is_deployed=False
            )
            
            # 7. Log de actividad
            ActivityLog.objects.create(
                tenant=tenant,
                user=request.user,
                action='create',
                description=f'Workspace {company_name} ({workspace_type}) creado',
                ip_address=get_client_ip(request)
            )
            
            messages.success(request, f'Workspace {company_name} creado exitosamente')
            return redirect('workspace_detail', tenant_id=tenant.id)
            
        except Exception as e:
            messages.error(request, f'Error al crear workspace: {str(e)}')
            return redirect('create_workspace')
    
    # GET request
    products = Product.objects.filter(is_active=True)
    users = User.objects.filter(is_active=True)
    
    context = {
        'products': products,
        'users': users,
    }
    return render(request, 'panel/create_workspace.html', context)


@login_required
@user_passes_test(is_superuser)
def workspace_detail(request, tenant_id):
    """Detalle de un workspace"""
    try:
        tenant = get_object_or_404(Tenant, id=tenant_id)
        tenant_users = TenantUser.objects.filter(tenant=tenant).select_related('user')
        activity = ActivityLog.objects.filter(tenant=tenant).order_by('-created_at')[:20]
        
        context = {
            'tenant': tenant,
            'tenant_users': tenant_users,
            'activity': activity,
        }
        return render(request, 'panel/workspace_detail.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar workspace: {str(e)}')
        return redirect('workspaces')


@login_required
@user_passes_test(is_superuser)
def workspace_action(request, tenant_id):
    """Acciones sobre un workspace"""
    if request.method == 'POST':
        try:
            tenant = get_object_or_404(Tenant, id=tenant_id)
            action = request.POST.get('action')
            
            if action == 'suspend':
                tenant.status = 'suspended'
                tenant.save()
                messages.success(request, f'Workspace {tenant.company_name} suspendido')
                
            elif action == 'activate':
                tenant.status = 'active'
                tenant.save()
                messages.success(request, f'Workspace {tenant.company_name} activado')
                
            elif action == 'delete':
                tenant.status = 'inactive'
                tenant.save()
                messages.success(request, f'Workspace {tenant.company_name} eliminado')
                
            ActivityLog.objects.create(
                tenant=tenant,
                user=request.user,
                action=action,
                description=f'Acción {action} ejecutada en {tenant.company_name}',
                ip_address=get_client_ip(request)
            )
            
            return redirect('workspace_detail', tenant_id=tenant.id)
        except Exception as e:
            messages.error(request, f'Error al ejecutar acción: {str(e)}')
            return redirect('workspaces')
    
    return redirect('workspaces')


@login_required
@user_passes_test(is_superuser)
def clients(request):
    """Lista de clientes"""
    try:
        users = User.objects.annotate(
            tenant_count=Count('owned_tenants')
        ).order_by('-date_joined')
        
        context = {
            'users': users,
        }
        return render(request, 'panel/clients.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar clientes: {str(e)}')
        return render(request, 'panel/clients.html', {'users': []})


@login_required
@user_passes_test(is_superuser)
def deployments(request):
    """Lista de deployments (por ahora muestra tenants agrupados)"""
    try:
        # Agrupar tenants por tipo
        dedicated_tenants = Tenant.objects.filter(type='dedicated').select_related('product', 'owner')
        shared_products = Product.objects.filter(is_active=True)
        
        context = {
            'dedicated_tenants': dedicated_tenants,
            'shared_products': shared_products,
        }
        return render(request, 'panel/deployments.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar deployments: {str(e)}')
        return render(request, 'panel/deployments.html', {})


@login_required
@user_passes_test(is_superuser)
def products(request):
    """Lista de productos"""
    try:
        all_products = Product.objects.annotate(
            tenant_count=Count('tenant')
        ).all()
        
        context = {
            'products': all_products,
        }
        return render(request, 'panel/products.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar productos: {str(e)}')
        return render(request, 'panel/products.html', {'products': []})


@login_required
@user_passes_test(is_superuser)
def databases(request):
    """Lista de bases de datos"""
    try:
        tenants = Tenant.objects.select_related('product').all()
        
        db_info = []
        for tenant in tenants:
            db_info.append({
                'tenant': tenant,
                'db_name': tenant.db_name,
                'db_user': tenant.db_user,
                'db_host': tenant.db_host,
                'db_port': tenant.db_port,
            })
        
        context = {
            'db_info': db_info,
        }
        return render(request, 'panel/databases.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar bases de datos: {str(e)}')
        return render(request, 'panel/databases.html', {'db_info': []})


@login_required
@user_passes_test(is_superuser)
def activity(request):
    """Log de actividades"""
    try:
        logs = ActivityLog.objects.select_related('user', 'tenant').order_by('-created_at')[:100]
        
        context = {
            'logs': logs,
        }
        return render(request, 'panel/activity.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar actividad: {str(e)}')
        return render(request, 'panel/activity.html', {'logs': []})


@login_required
@user_passes_test(is_superuser)
def settings_view(request):
    """Configuración del panel"""
    try:
        context = {
            'panel_domain': getattr(settings, 'PANEL_DOMAIN', 'panel.surgir.online'),
            'base_domain': getattr(settings, 'BASE_DOMAIN', 'surgir.online'),
        }
        return render(request, 'panel/settings.html', context)
    except Exception as e:
        messages.error(request, f'Error al cargar configuración: {str(e)}')
        return render(request, 'panel/settings.html', {})


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def create_database(db_name, db_user, db_password):
    """Crea una base de datos y usuario para el tenant"""
    try:
        conn = psycopg2.connect(
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT'],
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            database='postgres'
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        try:
            # Crear usuario
            cursor.execute(f"SELECT 1 FROM pg_roles WHERE rolname = '{db_user}'")
            if not cursor.fetchone():
                cursor.execute(f"CREATE USER {db_user} WITH PASSWORD '{db_password}'")
            
            # Crear database
            cursor.execute(f"SELECT 1 FROM pg_database WHERE datname = '{db_name}'")
            if not cursor.fetchone():
                cursor.execute(f"CREATE DATABASE {db_name} OWNER {db_user}")
            
            # Otorgar permisos
            cursor.execute(f"GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user}")
            
        finally:
            cursor.close()
            conn.close()
    except Exception as e:
        raise Exception(f"Error al crear base de datos: {str(e)}")


def get_client_ip(request):
    """Obtiene la IP del cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip