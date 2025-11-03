"""
Modelos para gestión de workspaces multi-tenant
Arquitectura Híbrida: Shared + Dedicated Containers
"""
from django.db import models
from django.contrib.auth.models import User
from django.core.validators import RegexValidator
from django.utils import timezone
import secrets
import string


def generate_password(length=24):
    """Genera contraseña segura para BD"""
    alphabet = string.ascii_letters + string.digits + "!@#$%^&*"
    return ''.join(secrets.choice(alphabet) for _ in range(length))


class Product(models.Model):
    """Productos disponibles (Inventario, ERP, Shop, etc)"""
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=200)
    subdomain_prefix = models.CharField(max_length=50, help_text="Ej: inv, erp, shop")
    
    # NUEVO: Configuración de contenedor compartido
    shared_container_port = models.IntegerField(
        default=8000,
        help_text="Puerto del contenedor compartido"
    )
    shared_container_name = models.CharField(
        max_length=100,
        default='app-shared',
        help_text="Nombre del contenedor compartido"
    )
    stack_path = models.CharField(
        max_length=500,
        default='/opt/stacks/',
        help_text="Ruta al stack en el VPS"
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
    
    # Campos existentes
    container_port = models.IntegerField(
        help_text="Puerto del contenedor (legacy - usar shared_container_port)"
    )
    version = models.CharField(max_length=20, default="1.0.0")
    docker_image = models.CharField(max_length=200, help_text="Imagen Docker", blank=True)
    is_active = models.BooleanField(default=True)
    icon = models.CharField(max_length=50, default='📦')
    description = models.TextField(blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        verbose_name = "Producto"
        verbose_name_plural = "Productos"
        ordering = ['name']
    
    def __str__(self):
        return self.display_name
    
    def get_available_port(self, deployment_type='shared'):
        """Obtiene puerto disponible según tipo de deployment"""
        if deployment_type == 'shared':
            return self.shared_container_port
        
        # Para dedicated, buscar puerto libre
        from django.db.models import Q
        used_ports = Workspace.objects.filter(
            product=self,
            deployment_type='dedicated'
        ).values_list('container_port', flat=True)
        
        for port in range(self.dedicated_port_start, self.dedicated_port_end + 1):
            if port not in used_ports:
                return port
        
        raise Exception(f"No hay puertos disponibles ({self.dedicated_port_start}-{self.dedicated_port_end})")


class Workspace(models.Model):
    """Espacio de trabajo = Tenant = Cliente"""
    
    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('paused', 'Pausado'),
        ('suspended', 'Suspendido'),
        ('cancelled', 'Cancelado'),
    ]
    
    PLAN_CHOICES = [
        ('free', 'Gratuito'),
        ('starter', 'Starter'),
        ('business', 'Business'),
        ('enterprise', 'Enterprise'),
        ('lifetime', 'Vitalicio'),
    ]
    
    # NUEVO: Tipo de deployment
    DEPLOYMENT_TYPES = [
        ('shared', 'Contenedor Compartido'),
        ('dedicated', 'Contenedor Dedicado'),
    ]
    
    product = models.ForeignKey(Product, on_delete=models.CASCADE, related_name='workspaces')
    company_name = models.CharField(max_length=200, verbose_name="Nombre de la empresa")
    subdomain = models.SlugField(
        max_length=100,
        validators=[
            RegexValidator(
                regex='^[a-z0-9-]+$',
                message='Solo letras minúsculas, números y guiones'
            )
        ],
        verbose_name="Subdominio"
    )
    
    # Configuración de base de datos
    db_name = models.CharField(max_length=100, unique=True)
    db_user = models.CharField(max_length=100)
    db_password = models.CharField(max_length=200)
    db_host = models.CharField(max_length=100, default='postgres16')
    db_port = models.IntegerField(default=5432)
    db_created = models.BooleanField(default=False)
    db_size_mb = models.FloatField(default=0.0, help_text="Tamaño de la BD en MB")
    
    # Configuración de contenedor Docker
    container_name = models.CharField(max_length=200, blank=True)
    container_id = models.CharField(max_length=200, blank=True)
    container_status = models.CharField(max_length=50, default='running')
    container_port = models.IntegerField(null=True, blank=True)
    
    # NUEVO: Tipo de deployment y stack
    deployment_type = models.CharField(
        max_length=20,
        choices=DEPLOYMENT_TYPES,
        default='shared',
        help_text="Tipo de despliegue del workspace"
    )
    stack_path = models.CharField(
        max_length=500,
        blank=True,
        help_text="Ruta del stack clonado (solo para dedicated)"
    )
    
    # Estado y plan
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')
    plan_type = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    
    # NUEVO: Historial de cambios de plan
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
        related_name='plan_changes_made',
        help_text="Usuario que cambió el plan"
    )
    
    # Fechas
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)
    paused_at = models.DateTimeField(null=True, blank=True)
    subscription_end = models.DateTimeField(null=True, blank=True)
    
    # Notas administrativas
    admin_notes = models.TextField(blank=True)
    
    class Meta:
        verbose_name = "Workspace"
        verbose_name_plural = "Workspaces"
        ordering = ['-created_at']
        unique_together = ['product', 'subdomain']
    
    def __str__(self):
        return f"{self.company_name} ({self.subdomain}.{self.product.subdomain_prefix})"
    
    @property
    def url(self):
        """URL completa del workspace"""
        from django.conf import settings
        domain = settings.TENANT_DOMAIN
        return f"https://{self.subdomain}.{self.product.subdomain_prefix}.{domain}"
    
    @property
    def full_subdomain(self):
        """Subdominio completo"""
        return f"{self.subdomain}.{self.product.subdomain_prefix}"
    
    @property
    def is_subscription(self):
        """Verifica si tiene suscripción activa"""
        return self.plan_type not in ['free', 'lifetime']
    
    @property
    def days_remaining(self):
        """Días restantes de suscripción"""
        if self.plan_type == 'lifetime' or not self.subscription_end:
            return None
        delta = self.subscription_end - timezone.now()
        return max(0, delta.days)
    
    @property
    def deployment_type_display(self):
        """Mostrar tipo de deployment con icono"""
        if self.deployment_type == 'dedicated':
            return "🚀 Dedicado"
        return "📦 Compartido"
    
    def pause(self):
        """Pausar workspace"""
        self.status = 'paused'
        self.paused_at = timezone.now()
        self.save()
    
    def resume(self):
        """Reanudar workspace"""
        self.status = 'active'
        self.paused_at = None
        self.save()
    
    def can_upgrade(self):
        """Retorna lista de planes a los que puede hacer upgrade"""
        upgrades = {
            'free': ['starter', 'business', 'enterprise', 'lifetime'],
            'starter': ['business', 'enterprise', 'lifetime'],
            'business': ['enterprise', 'lifetime'],
            'enterprise': ['lifetime'],
            'lifetime': []
        }
        return upgrades.get(self.plan_type, [])
    
    def can_downgrade(self):
        """Retorna lista de planes a los que puede hacer downgrade"""
        downgrades = {
            'enterprise': ['business', 'starter'],
            'business': ['starter'],
            'starter': ['free'],
            'free': [],
            'lifetime': []  # Lifetime no puede downgrade
        }
        return downgrades.get(self.plan_type, [])
    
    def requires_migration(self, new_plan):
        """
        Verifica si cambiar al nuevo plan requiere migración de contenedor
        
        Regla: Enterprise y Lifetime usan contenedores dedicados
               Los demás usan contenedor compartido
        """
        current_needs_dedicated = self.plan_type in ['enterprise', 'lifetime']
        new_needs_dedicated = new_plan in ['enterprise', 'lifetime']
        
        return current_needs_dedicated != new_needs_dedicated
    
    def get_plan_info(self):
        """Información detallada del plan actual"""
        plans_info = {
            'free': {
                'name': 'Gratuito',
                'price': '$0',
                'storage': '1 GB',
                'users': '5',
                'deployment': 'shared',
                'color': 'gray'
            },
            'starter': {
                'name': 'Starter',
                'price': '$19/mes',
                'storage': '10 GB',
                'users': '20',
                'deployment': 'shared',
                'color': 'blue'
            },
            'business': {
                'name': 'Business',
                'price': '$49/mes',
                'storage': '50 GB',
                'users': 'Ilimitados',
                'deployment': 'shared',
                'color': 'green'
            },
            'enterprise': {
                'name': 'Enterprise',
                'price': '$199/mes',
                'storage': '200 GB',
                'users': 'Ilimitados',
                'deployment': 'dedicated',
                'color': 'purple'
            },
            'lifetime': {
                'name': 'Vitalicio',
                'price': '$999 único',
                'storage': '500 GB',
                'users': 'Ilimitados',
                'deployment': 'dedicated',
                'color': 'yellow'
            }
        }
        return plans_info.get(self.plan_type, plans_info['free'])


class WorkspaceMembership(models.Model):
    """Membresía de usuario en un workspace"""
    
    ROLE_CHOICES = [
        ('owner', 'Propietario'),
        ('admin', 'Administrador'),
        ('member', 'Miembro'),
        ('viewer', 'Visualizador'),
    ]
    
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='workspace_memberships')
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='member')
    joined_at = models.DateTimeField(auto_now_add=True)
    is_active = models.BooleanField(default=True)
    
    class Meta:
        unique_together = ['user', 'workspace']
        verbose_name = "Membresía"
        verbose_name_plural = "Membresías"
        ordering = ['-joined_at']
    
    def __str__(self):
        return f"{self.user.username} - {self.workspace.company_name} ({self.role})"


class DatabaseBackup(models.Model):
    """Backups de bases de datos"""
    
    workspace = models.ForeignKey(Workspace, on_delete=models.CASCADE, related_name='backups')
    filename = models.CharField(max_length=255)
    file_path = models.CharField(max_length=500)
    size_mb = models.FloatField(default=0.0)
    backup_type = models.CharField(max_length=20, choices=[
        ('manual', 'Manual'),
        ('automatic', 'Automático'),
    ], default='manual')
    created_by = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    notes = models.TextField(blank=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Backup de Base de Datos"
        verbose_name_plural = "Backups de Bases de Datos"
    
    def __str__(self):
        return f"Backup {self.workspace.company_name} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class ActivityLog(models.Model):
    """Log de actividades administrativas"""
    
    ACTION_CHOICES = [
        ('create', 'Crear'),
        ('update', 'Actualizar'),
        ('delete', 'Eliminar'),
        ('pause', 'Pausar'),
        ('resume', 'Reanudar'),
        ('backup', 'Backup'),
        ('restore', 'Restaurar'),
        ('migrate', 'Migrar'),  # NUEVO
        ('plan_change', 'Cambio de Plan'),  # NUEVO
    ]
    
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True)
    workspace = models.ForeignKey(Workspace, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Log de Actividad"
        verbose_name_plural = "Logs de Actividad"
    
    def __str__(self):
        return f"{self.action} - {self.user} - {self.created_at.strftime('%Y-%m-%d %H:%M')}"


class PlanChange(models.Model):
    """Historial de cambios de plan"""
    
    workspace = models.ForeignKey(
        Workspace,
        on_delete=models.CASCADE,
        related_name='plan_change_history'
    )
    changed_by = models.ForeignKey(
        User,
        on_delete=models.SET_NULL,
        null=True,
        related_name='plan_changes_executed'
    )
    
    old_plan = models.CharField(max_length=20)
    new_plan = models.CharField(max_length=20)
    old_deployment = models.CharField(max_length=20)
    new_deployment = models.CharField(max_length=20)
    
    migration_required = models.BooleanField(default=False)
    migration_success = models.BooleanField(default=True)
    migration_notes = models.TextField(blank=True)
    
    reason = models.TextField(blank=True, help_text="Razón del cambio de plan")
    created_at = models.DateTimeField(auto_now_add=True)
    
    class Meta:
        ordering = ['-created_at']
        verbose_name = "Cambio de Plan"
        verbose_name_plural = "Cambios de Plan"
    
    def __str__(self):
        migration = " (con migración)" if self.migration_required else ""
        return f"{self.workspace.company_name}: {self.old_plan} → {self.new_plan}{migration}"
    
    @property
    def is_upgrade(self):
        """Determina si fue un upgrade"""
        plan_order = ['free', 'starter', 'business', 'enterprise', 'lifetime']
        try:
            old_idx = plan_order.index(self.old_plan)
            new_idx = plan_order.index(self.new_plan)
            return new_idx > old_idx
        except ValueError:
            return False
