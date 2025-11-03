from django.shortcuts import render, redirect
from django.contrib.auth import login
from django.contrib.auth.decorators import login_required
from django.contrib import messages
from django.conf import settings
from .forms import RegisterForm
from .models import Workspace, WorkspaceMembership
from .utils import create_tenant_database
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
                subdomain = form.get_subdomain()  # Auto-generado desde company_name
                
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
                )
                
                # 5. Asignar usuario como owner
                WorkspaceMembership.objects.create(
                    user=user,
                    workspace=workspace,
                    role='owner'
                )
                
                # 6. Login automático
                login(request, user)
                
                messages.success(
                    request,
                    f'¡Bienvenido! Tu espacio de trabajo está listo.'
                )
                
                # 7. Redirigir al workspace
                return redirect('workspace_ready', workspace_id=workspace.id)
                
            except Exception as e:
                logger.error(f"Error al crear workspace: {e}")
                messages.error(request, f"Error al crear el espacio de trabajo: {str(e)}")
                # Rollback: eliminar usuario si se creó
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
        user=request.user
    ).select_related('workspace', 'workspace__product')
    
    return render(request, 'accounts/dashboard.html', {
        'memberships': memberships
    })


@login_required
def workspace_ready(request, workspace_id):
    """Página de confirmación de workspace creado"""
    try:
        membership = WorkspaceMembership.objects.select_related('workspace', 'workspace__product').get(
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
