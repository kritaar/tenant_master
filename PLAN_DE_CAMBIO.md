# 🚀 PLAN DE CAMBIO COMPLETO - TENANT MASTER

## 📋 RESUMEN EJECUTIVO

### Cambios a Implementar:
1. ✅ **Arquitectura Híbrida** (Shared + Dedicated Containers)
2. ✅ **Sistema de Migración de Planes**
3. ✅ **Frontend 100% Responsive**
4. ✅ **Templates Faltantes Completos**
5. ✅ **Gestión Automática de Puertos**
6. ✅ **Deploy/Undeploy de Contenedores**

---

## 🏗️ CAMBIO 1: MODELOS (models.py)

### Campos Nuevos en `Product`:

```python
class Product(models.Model):
    # ... campos existentes ...
    
    # NUEVO: Configuración para contenedores compartidos
    shared_container_port = models.IntegerField(
        help_text="Puerto del contenedor compartido",
        default=8000
    )
    shared_container_name = models.CharField(
        max_length=100,
        help_text="Nombre del contenedor compartido"
    )
    stack_path = models.CharField(
        max_length=500,
        help_text="Ruta al stack en /opt/stacks/",
        default="/opt/stacks/"
    )
    
    # NUEVO: Rango de puertos para contenedores dedicados
    dedicated_port_start = models.IntegerField(
        default=8100,
        help_text="Puerto inicial para contenedores dedicados"
    )
    dedicated_port_end = models.IntegerField(
        default=8199,
        help_text="Puerto final para contenedores dedicados"
    )
```

### Campos Nuevos en `Workspace`:

```python
class Workspace(models.Model):
    # ... campos existentes ...
    
    # NUEVO: Tipo de despliegue
    DEPLOYMENT_TYPES = [
        ('shared', 'Contenedor Compartido'),
        ('dedicated', 'Contenedor Dedicado'),
    ]
    
    deployment_type = models.CharField(
        max_length=20,
        choices=DEPLOYMENT_TYPES,
        default='shared',
        help_text="Tipo de despliegue del workspace"
    )
    
    # NUEVO: Path del stack (solo para dedicated)
    stack_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Ruta del stack clonado (solo dedicated)"
    )
    
    # NUEVO: Información de migración
    previous_plan = models.CharField(
        max_length=20,
        blank=True,
        help_text="Plan anterior (para historial)"
    )
    plan_changed_at = models.DateTimeField(
        null=True,
        blank=True,
        help_text="Fecha del último cambio de plan"
    )
    plan_changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        blank=True,
        related_name='plan_changes',
        help_text="Usuario que cambió el plan"
    )
    
    # Métodos nuevos
    def can_upgrade(self):
        """Verifica si puede hacer upgrade de plan"""
        upgrades = {
            'free': ['starter', 'business', 'enterprise', 'lifetime'],
            'starter': ['business', 'enterprise', 'lifetime'],
            'business': ['enterprise', 'lifetime'],
            'enterprise': ['lifetime'],
            'lifetime': []
        }
        return upgrades.get(self.plan_type, [])
    
    def can_downgrade(self):
        """Verifica si puede hacer downgrade de plan"""
        downgrades = {
            'enterprise': ['business', 'starter'],
            'business': ['starter'],
            'starter': ['free'],
            'free': [],
            'lifetime': []
        }
        return downgrades.get(self.plan_type, [])
    
    def requires_migration(self, new_plan):
        """Verifica si requiere migración de contenedor"""
        current_needs_dedicated = self.plan_type in ['enterprise', 'lifetime']
        new_needs_dedicated = new_plan in ['enterprise', 'lifetime']
        return current_needs_dedicated != new_needs_dedicated
```

### Nuevo Modelo: `PlanChange`

```python
class PlanChange(models.Model):
    """Historial de cambios de plan"""
    
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='plan_changes'
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True
    )
    
    old_plan = models.CharField(max_length=20)
    new_plan = models.CharField(max_length=20)
    old_deployment = models.CharField(max_length=20)
    new_deployment = models.CharField(max_length=20)
    
    reason = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
    
    def __str__(self):
        return f"{self.workspace.company_name}: {self.old_plan} → {self.new_plan}"
```

---

## 🔧 CAMBIO 2: UTILIDADES (utils.py)

### Nuevas Funciones:

```python
def get_available_port(product, deployment_type='shared'):
    """
    Obtiene puerto disponible según el tipo de deployment
    """
    if deployment_type == 'shared':
        return product.shared_container_port
    
    # Para dedicated, buscar puerto libre en el rango
    used_ports = Workspace.objects.filter(
        product=product,
        deployment_type='dedicated'
    ).values_list('container_port', flat=True)
    
    for port in range(product.dedicated_port_start, product.dedicated_port_end + 1):
        if port not in used_ports:
            return port
    
    raise Exception(f"No hay puertos disponibles en el rango {product.dedicated_port_start}-{product.dedicated_port_end}")


def clone_and_deploy_stack(product, workspace_slug, port, db_credentials):
    """
    Clona stack y despliega contenedor dedicado
    """
    import shutil
    import yaml
    import subprocess
    
    # 1. Clonar directorio
    source = product.stack_path
    dest = f"/opt/stacks/{product.name}-{workspace_slug}/"
    
    shutil.copytree(source, dest)
    
    # 2. Configurar docker-compose.yml
    compose_file = os.path.join(dest, 'docker-compose.yml')
    
    with open(compose_file, 'r') as f:
        compose = yaml.safe_load(f)
    
    # Actualizar configuración
    service_name = list(compose['services'].keys())[0]
    compose['services'][service_name]['ports'] = [f"{port}:8000"]
    compose['services'][service_name]['container_name'] = f"{product.name}_{workspace_slug}"
    compose['services'][service_name]['environment'].update({
        'DB_NAME': db_credentials['db_name'],
        'DB_USER': db_credentials['db_user'],
        'DB_PASSWORD': db_credentials['db_password'],
    })
    
    with open(compose_file, 'w') as f:
        yaml.dump(compose, f)
    
    # 3. Levantar stack
    subprocess.run(
        ['docker-compose', 'up', '-d'],
        cwd=dest,
        check=True
    )
    
    return dest


def undeploy_stack(stack_path):
    """
    Detiene y elimina un stack dedicado
    """
    import subprocess
    import shutil
    
    # 1. Detener contenedores
    subprocess.run(
        ['docker-compose', 'down'],
        cwd=stack_path
    )
    
    # 2. Eliminar directorio
    shutil.rmtree(stack_path)


def migrate_to_dedicated(workspace):
    """
    Migra workspace de shared a dedicated
    """
    # 1. Obtener puerto disponible
    port = get_available_port(workspace.product, 'dedicated')
    
    # 2. Clonar y desplegar stack
    db_credentials = {
        'db_name': workspace.db_name,
        'db_user': workspace.db_user,
        'db_password': workspace.db_password,
    }
    
    stack_path = clone_and_deploy_stack(
        workspace.product,
        workspace.subdomain,
        port,
        db_credentials
    )
    
    # 3. Actualizar workspace
    workspace.deployment_type = 'dedicated'
    workspace.container_port = port
    workspace.container_name = f"{workspace.product.name}_{workspace.subdomain}"
    workspace.stack_path = stack_path
    workspace.save()
    
    # 4. Configurar nginx
    configure_nginx_route(workspace)
    
    return True


def migrate_to_shared(workspace):
    """
    Migra workspace de dedicated a shared
    """
    # 1. Eliminar stack dedicado
    if workspace.stack_path:
        undeploy_stack(workspace.stack_path)
    
    # 2. Actualizar workspace
    workspace.deployment_type = 'shared'
    workspace.container_port = workspace.product.shared_container_port
    workspace.container_name = workspace.product.shared_container_name
    workspace.stack_path = ''
    workspace.save()
    
    # 3. Remover configuración nginx específica
    remove_nginx_route(workspace)
    
    return True
```

---

## 🎯 CAMBIO 3: VISTAS (views.py)

### Nueva Vista: Cambiar Plan

```python
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
            workspace.plan_changed_at = timezone.now()
            workspace.plan_changed_by = request.user
            
            # Verificar si necesita migración de contenedor
            if workspace.requires_migration(new_plan):
                if new_plan in ['enterprise', 'lifetime']:
                    # Migrar a dedicated
                    migrate_to_dedicated(workspace)
                    messages.success(
                        request,
                        f'✅ Plan actualizado y migrado a contenedor dedicado'
                    )
                else:
                    # Migrar a shared
                    migrate_to_shared(workspace)
                    messages.success(
                        request,
                        f'✅ Plan actualizado y migrado a contenedor compartido'
                    )
            else:
                workspace.save()
                messages.success(request, f'✅ Plan actualizado a {new_plan}')
            
            # Registrar cambio de plan
            PlanChange.objects.create(
                workspace=workspace,
                changed_by=request.user,
                old_plan=old_plan,
                new_plan=new_plan,
                old_deployment=old_deployment,
                new_deployment=workspace.deployment_type,
                reason=reason
            )
            
            # Log de actividad
            ActivityLog.objects.create(
                user=request.user,
                workspace=workspace,
                action='update',
                description=f'Plan cambiado: {old_plan} → {new_plan} ({old_deployment} → {workspace.deployment_type})',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            logger.error(f"Error cambiando plan: {e}", exc_info=True)
    
    return redirect('admin_workspace_detail', workspace_id)
```

### Actualizar: admin_create_workspace

```python
@login_required
@user_passes_test(is_staff_user)
def admin_create_workspace(request):
    """Crear workspace con arquitectura híbrida"""
    
    if request.method == 'POST':
        company_name = request.POST.get('company_name')
        product_id = request.POST.get('product')
        subdomain = request.POST.get('subdomain')
        plan_type = request.POST.get('plan_type', 'free')
        
        try:
            product = Product.objects.get(id=product_id)
            
            # Determinar tipo de deployment
            deployment_type = 'dedicated' if plan_type in ['enterprise', 'lifetime'] else 'shared'
            
            # 1. Crear base de datos
            db_credentials = create_tenant_database(
                product.name,
                subdomain,
                company_name
            )
            
            # 2. Obtener puerto y configuración
            port = get_available_port(product, deployment_type)
            
            if deployment_type == 'dedicated':
                # Clonar y desplegar stack
                stack_path = clone_and_deploy_stack(
                    product,
                    subdomain,
                    port,
                    db_credentials
                )
                container_name = f"{product.name}_{subdomain}"
            else:
                # Usar contenedor compartido
                stack_path = ''
                container_name = product.shared_container_name
            
            # 3. Crear workspace
            workspace = Workspace.objects.create(
                product=product,
                company_name=company_name,
                subdomain=subdomain,
                plan_type=plan_type,
                deployment_type=deployment_type,
                container_name=container_name,
                container_port=port,
                stack_path=stack_path,
                db_name=db_credentials['db_name'],
                db_user=db_credentials['db_user'],
                db_password=db_credentials['db_password'],
                db_created=True,
                status='active',
            )
            
            # 4. Aplicar migraciones
            run_migrations_for_tenant(workspace)
            
            # 5. Configurar Nginx (solo si es dedicated)
            if deployment_type == 'dedicated':
                configure_nginx_route(workspace)
            
            # 6. Log
            ActivityLog.objects.create(
                user=request.user,
                workspace=workspace,
                action='create',
                description=f'Workspace creado ({deployment_type}): {workspace.company_name}',
                ip_address=request.META.get('REMOTE_ADDR')
            )
            
            messages.success(
                request,
                f'✅ Workspace creado! Tipo: {deployment_type.upper()}<br>'
                f'URL: https://{workspace.full_subdomain}.kitagli.com'
            )
            
            return redirect('admin_workspace_detail', workspace.id)
            
        except Exception as e:
            messages.error(request, f'Error: {str(e)}')
            logger.error(f"Error creando workspace: {e}", exc_info=True)
    
    products = Product.objects.filter(is_active=True)
    return render(request, 'accounts/admin/create_workspace.html', {
        'products': products
    })
```

---

## 🎨 CAMBIO 4: TEMPLATES RESPONSIVE

### Todos los templates tendrán:
- ✅ Mobile-first design
- ✅ Hamburger menu en móvil
- ✅ Grids responsivos
- ✅ Tablas scrollables
- ✅ Cards adaptables
- ✅ Modales responsive

---

## 📊 CAMBIO 5: URLS

```python
# accounts/urls.py - AGREGAR

urlpatterns = [
    # ... existentes ...
    
    # NUEVO: Cambio de plan
    path('admin/workspace/<int:workspace_id>/change-plan/', 
         views.admin_change_plan, 
         name='admin_change_plan'),
]
```

---

## 📝 ARCHIVOS A CREAR/MODIFICAR

### ✅ ARCHIVOS A MODIFICAR:
1. `accounts/models.py` - Agregar campos nuevos
2. `accounts/views.py` - Agregar vistas de migración
3. `accounts/utils.py` - Agregar funciones de deploy
4. `accounts/urls.py` - Agregar rutas nuevas
5. `accounts/admin.py` - Registrar PlanChange

### ✅ TEMPLATES A CREAR (100% Responsive):
1. `admin/workspace_detail.html` - COMPLETAR (está vacío)
2. `admin/database_manager.html` - CREAR
3. `admin/activity_log.html` - CREAR
4. `admin/products.html` - CREAR
5. `admin/create_workspace.html` - CREAR
6. `admin/change_plan_modal.html` - CREAR

### ✅ TEMPLATES A ACTUALIZAR (Responsive):
1. `base.html` - Agregar hamburger menu
2. `admin/base_admin.html` - Responsive navbar
3. `admin/dashboard.html` - Ya existe, hacer responsive
4. `dashboard.html` - Ya existe, mejorar responsive

---

## 🚀 ORDEN DE IMPLEMENTACIÓN

### FASE 1: Backend (1-2 horas)
1. ✅ Modificar models.py
2. ✅ Crear migraciones: `python manage.py makemigrations`
3. ✅ Aplicar migraciones: `python manage.py migrate`
4. ✅ Actualizar utils.py
5. ✅ Actualizar views.py
6. ✅ Actualizar urls.py

### FASE 2: Templates (2-3 horas)
1. ✅ Actualizar base.html (responsive)
2. ✅ Completar workspace_detail.html
3. ✅ Crear database_manager.html
4. ✅ Crear activity_log.html
5. ✅ Crear products.html
6. ✅ Crear create_workspace.html
7. ✅ Crear change_plan_modal.html

### FASE 3: Testing (30 min)
1. ✅ Crear workspace shared
2. ✅ Crear workspace dedicated
3. ✅ Migrar de shared a dedicated
4. ✅ Migrar de dedicated a shared
5. ✅ Probar responsive en móvil/tablet

---

## 💡 CARACTERÍSTICAS FINALES

### ✅ Arquitectura Híbrida:
- Planes Free/Starter/Business → Shared container
- Planes Enterprise/Lifetime → Dedicated container
- Migración automática al cambiar plan

### ✅ Sistema de Migración:
- Botón "Cambiar Plan" en cada workspace
- Modal con opciones de upgrade/downgrade
- Migración automática de contenedores
- Historial de cambios de plan

### ✅ Frontend Responsive:
- Mobile: < 640px
- Tablet: 640px - 1024px
- Desktop: > 1024px
- Todo funcional en cualquier dispositivo

### ✅ Gestión Completa:
- Crear workspaces (shared o dedicated)
- Cambiar planes con migración automática
- Pausar/reanudar workspaces
- Backups de bases de datos
- Logs de actividad completos

---

## 📦 ESTRUCTURA FINAL

```
/opt/stacks/
├── tenant-master/              (Puerto 8001)
├── inventario-system/          (Puerto 8100 - SHARED)
├── inventario-cliente-enterprise/ (Puerto 8105 - DEDICATED)
├── erp-system/                 (Puerto 8200 - SHARED)
├── erp-megacorp/              (Puerto 8205 - DEDICATED)
├── shop-system/               (Puerto 8300 - SHARED)
└── landing-builder/           (Puerto 8400 - SHARED)

PostgreSQL:
├── tenant_master
├── inventario_cliente1         (shared)
├── inventario_cliente2         (shared)
├── inventario_cliente_enterprise (dedicated)
├── erp_cliente1                (shared)
└── erp_megacorp                (dedicated)
```

---

¿Quieres que empiece a implementar estos cambios? 

Puedo hacerlo en este orden:
1. Primero el backend (modelos, vistas, utils)
2. Luego los templates responsive
3. Finalmente testing

¿Comenzamos? 🚀
