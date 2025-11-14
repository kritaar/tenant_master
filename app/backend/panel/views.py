"""
Views del Panel de Administración Tenant Master
Actualizado con soporte para Deployments
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
import requests
import subprocess
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
import secrets
import string
import os


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
    total_tenants = Tenant.objects.count()
    active_tenants = Tenant.objects.filter(status='ACTIVE').count()
    
    # Contar por tipo de deployment
    dedicated_count = Deployment.objects.filter(deployment_type='DEDICATED').count()
    shared_count = Deployment.objects.filter(deployment_type='SHARED').count()
    
    recent_tenants = Tenant.objects.select_related('product', 'owner', 'deployment').order_by('-created_at')[:10]
    recent_activity = ActivityLog.objects.select_related('user', 'tenant').order_by('-created_at')[:10]
    
    context = {
        'total_tenants': total_tenants,
        'active_tenants': active_tenants,
        'dedicated_deployments': dedicated_count,
        'shared_deployments': shared_count,
        'recent_tenants': recent_tenants,
        'recent_activity': recent_activity,
    }
    return render(request, 'panel/dashboard.html', context)


@login_required
@user_passes_test(is_superuser)
def workspaces(request):
    tenants = Tenant.objects.select_related('product', 'owner', 'deployment').all()
    products = Product.objects.filter(is_active=True)
    
    context = {
        'tenants': tenants,
        'products': products,
    }
    return render(request, 'panel/workspaces.html', context)


@login_required
@user_passes_test(is_superuser)
def create_workspace(request):
    """
    Crea un nuevo workspace con su deployment correspondiente
    """
    if request.method == 'POST':
        try:
            # 1. Recoger datos del formulario
            company_name = request.POST.get('company_name')
            subdomain = request.POST.get('subdomain').lower()
            product_id = request.POST.get('product')
            plan = request.POST.get('plan', 'free')
            deployment_type = request.POST.get('deployment_type', 'DEDICATED')  # SHARED o DEDICATED
            owner_username = request.POST.get('owner_username')
            
            # 2. Validaciones
            if Tenant.objects.filter(subdomain=subdomain).exists():
                messages.error(request, f'El subdominio {subdomain} ya existe')
                return redirect('create_workspace')
            
            product = Product.objects.get(id=product_id)
            owner = User.objects.get(username=owner_username)
            
            # 3. Generar nombres únicos
            schema_name = f"tenant_{subdomain}"
            db_name = schema_name
            db_user = f"user_{subdomain}"
            db_password = generate_password()
            
            # 4. Crear o usar deployment
            if deployment_type == 'SHARED':
                # Buscar deployment compartido disponible
                deployment = Deployment.objects.filter(
                    product=product,
                    deployment_type='SHARED',
                    status='ACTIVE'
                ).first()
                
                if not deployment or not deployment.is_available:
                    messages.error(request, 'No hay deployments compartidos disponibles')
                    return redirect('create_workspace')
                
                # Incrementar contador
                deployment.current_tenants += 1
                deployment.save()
                
            else:  # DEDICATED
                # Crear nuevo deployment dedicado
                deployment = Deployment.objects.create(
                    name=f"{product.name.lower()}-{schema_name}",
                    product=product,
                    deployment_type='DEDICATED',
                    status='DEPLOYING',
                    physical_path=f"/var/deployments/{product.name.lower()}-{schema_name}",
                    docker_compose_content='',  # Se llenará en el script
                    max_tenants=1,
                    current_tenants=1
                )
            
            # 5. Crear base de datos
            create_database(db_name, db_user, db_password)
            
            # 6. Crear tenant
            tenant = Tenant.objects.create(
                name=company_name,
                subdomain=subdomain,
                company_name=company_name,
                product=product,
                deployment=deployment,
                plan=plan,
                status='ACTIVE',
                schema_name=schema_name,
                db_name=db_name,
                db_user=db_user,
                db_password=db_password,
                owner=owner
            )
            
            # 7. Log de actividad
            ActivityLog.objects.create(
                tenant=tenant,
                deployment=deployment,
                user=request.user,
                action='create',
                description=f'Workspace {company_name} creado con deployment {deployment.name}',
                ip_address=get_client_ip(request)
            )
            
            # 8. Si es DEDICATED, ejecutar script de despliegue
            if deployment_type == 'DEDICATED':
                try:
                    # Ejecutar script de despliegue en background
                    script_path = os.path.join(settings.BASE_DIR, '..', '..', 'infra', 'scripts', 'deploy_product.py')
                    subprocess.Popen(['python', script_path, '--workspace-id', str(tenant.id)])
                    
                    messages.success(request, f'Workspace {company_name} creado. El despliegue está en proceso...')
                except Exception as e:
                    messages.warning(request, f'Workspace creado pero error al iniciar despliegue: {str(e)}')
            else:
                messages.success(request, f'Workspace {company_name} creado exitosamente en deployment compartido')
            
            return redirect('workspace_detail', tenant_id=tenant.id)
            
        except Exception as e:
            messages.error(request, f'Error al crear workspace: {str(e)}')
            return redirect('create_workspace')
    
    # GET request
    products = Product.objects.filter(is_active=True)
    users = User.objects.filter(is_active=True)
    
    # Listar deployments compartidos disponibles por producto
    shared_deployments = {}
    for product in products:
        deployments = Deployment.objects.filter(
            product=product,
            deployment_type='SHARED',
            status='ACTIVE'
        )
        available = [d for d in deployments if d.is_available]
        shared_deployments[product.id] = len(available)
    
    context = {
        'products': products,
        'users': users,
        'shared_deployments': shared_deployments,
    }
    return render(request, 'panel/create_workspace.html', context)


@login_required
@user_passes_test(is_superuser)
def workspace_detail(request, tenant_id):
    tenant = get_object_or_404(Tenant, id=tenant_id)
    tenant_users = TenantUser.objects.filter(tenant=tenant).select_related('user')
    activity = ActivityLog.objects.filter(tenant=tenant).order_by('-created_at')[:20]
    
    context = {
        'tenant': tenant,
        'tenant_users': tenant_users,
        'activity': activity,
    }
    return render(request, 'panel/workspace_detail.html', context)


@login_required
@user_passes_test(is_superuser)
def workspace_action(request, tenant_id):
    if request.method == 'POST':
        tenant = get_object_or_404(Tenant, id=tenant_id)
        action = request.POST.get('action')
        
        if action == 'suspend':
            tenant.status = 'SUSPENDED'
            tenant.save()
            messages.success(request, f'Workspace {tenant.company_name} suspendido')
            
        elif action == 'activate':
            tenant.status = 'ACTIVE'
            tenant.save()
            messages.success(request, f'Workspace {tenant.company_name} activado')
            
        elif action == 'delete':
            # Decrementar contador de deployment si es compartido
            if tenant.deployment.deployment_type == 'SHARED':
                tenant.deployment.current_tenants -= 1
                tenant.deployment.save()
            
            tenant.status = 'INACTIVE'
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
    
    return redirect('workspaces')


@login_required
@user_passes_test(is_superuser)
def clients(request):
    users = User.objects.annotate(
        tenant_count=Count('owned_tenants')
    ).order_by('-date_joined')
    
    context = {
        'users': users,
    }
    return render(request, 'panel/clients.html', context)


@login_required
@user_passes_test(is_superuser)
def deployments(request):
    """Lista todos los deployments"""
    all_deployments = Deployment.objects.select_related('product').annotate(
        tenant_count=Count('tenants')
    ).order_by('-created_at')
    
    context = {
        'deployments': all_deployments,
        'portainer_configured': bool(settings.PORTAINER_BASE and settings.PORTAINER_API_KEY),
    }
    return render(request, 'panel/deployments.html', context)


@login_required
@user_passes_test(is_superuser)
def products(request):
    all_products = Product.objects.annotate(
        deployment_count=Count('deployments'),
        tenant_count=Count('tenant')
    ).all()
    
    context = {
        'products': all_products,
    }
    return render(request, 'panel/products.html', context)


@login_required
@user_passes_test(is_superuser)
def databases(request):
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


@login_required
@user_passes_test(is_superuser)
def activity(request):
    logs = ActivityLog.objects.select_related('user', 'tenant', 'deployment').order_by('-created_at')[:100]
    
    context = {
        'logs': logs,
    }
    return render(request, 'panel/activity.html', context)


@login_required
@user_passes_test(is_superuser)
def settings_view(request):
    context = {
        'panel_domain': settings.PANEL_DOMAIN,
        'base_domain': settings.BASE_DOMAIN,
        'portainer_configured': bool(settings.PORTAINER_BASE and settings.PORTAINER_API_KEY),
    }
    return render(request, 'panel/settings.html', context)


# ============================================
# FUNCIONES AUXILIARES
# ============================================

def create_database(db_name, db_user, db_password):
    """Crea una base de datos y usuario para el tenant"""
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


def get_portainer_stacks():
    """Obtiene stacks de Portainer"""
    if not settings.PORTAINER_BASE or not settings.PORTAINER_API_KEY:
        return []
    
    url = f"{settings.PORTAINER_BASE}/api/stacks"
    headers = {
        'X-API-Key': settings.PORTAINER_API_KEY
    }
    
    response = requests.get(url, headers=headers, timeout=10)
    
    if response.status_code == 200:
        return response.json()
    
    return []


def get_client_ip(request):
    """Obtiene la IP del cliente"""
    x_forwarded_for = request.META.get('HTTP_X_FORWARDED_FOR')
    if x_forwarded_for:
        ip = x_forwarded_for.split(',')[0]
    else:
        ip = request.META.get('REMOTE_ADDR')
    return ip
