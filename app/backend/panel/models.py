from django.db import models
from django.contrib.auth.models import User
from django.utils import timezone

class Product(models.Model):
    name = models.CharField(max_length=100, unique=True)
    display_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)
    icon = models.CharField(max_length=10, default='📦')
    docker_image = models.CharField(max_length=200, blank=True)
    template_path = models.CharField(max_length=255, blank=True, help_text="Path en /opt/proyectos/")
    github_repo_url = models.CharField(max_length=500, blank=True, help_text="URL del repositorio GitHub del código base")
    is_active = models.BooleanField(default=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'panel_product'
        ordering = ['display_name']

    def __str__(self):
        return self.display_name

class Tenant(models.Model):
    TYPE_CHOICES = [
        ('shared', 'Compartido'),
        ('dedicated', 'Dedicado'),
    ]

    STATUS_CHOICES = [
        ('active', 'Activo'),
        ('suspended', 'Suspendido'),
        ('inactive', 'Inactivo'),
    ]

    PLAN_CHOICES = [
        ('free', 'Gratuito'),
        ('starter', 'Starter'),
        ('professional', 'Profesional'),
        ('enterprise', 'Enterprise'),
    ]

    name = models.CharField(max_length=100)
    subdomain = models.CharField(max_length=100, unique=True)
    company_name = models.CharField(max_length=200)
    product = models.ForeignKey(Product, on_delete=models.PROTECT)
    plan = models.CharField(max_length=20, choices=PLAN_CHOICES, default='free')
    type = models.CharField(max_length=20, choices=TYPE_CHOICES, default='dedicated')
    status = models.CharField(max_length=20, choices=STATUS_CHOICES, default='active')

    db_name = models.CharField(max_length=100, unique=True)
    db_user = models.CharField(max_length=100, blank=True)
    db_password = models.CharField(max_length=255, blank=True)
    db_host = models.CharField(max_length=200, default='postgres')
    db_port = models.IntegerField(default=5432)

    project_path = models.CharField(max_length=500, blank=True)
    stack_path = models.CharField(max_length=500, blank=True)
    git_repo_url = models.CharField(max_length=500, blank=True)
    
    stack_name = models.CharField(max_length=100, blank=True)
    portainer_stack_id = models.IntegerField(null=True, blank=True)

    owner = models.ForeignKey(User, on_delete=models.PROTECT, related_name='owned_tenants')

    max_users = models.IntegerField(default=5)
    storage_limit_gb = models.IntegerField(default=10)
    
    is_deployed = models.BooleanField(default=False)
    deployed_at = models.DateTimeField(null=True, blank=True)

    created_at = models.DateTimeField(auto_now_add=True)
    updated_at = models.DateTimeField(auto_now=True)

    class Meta:
        db_table = 'panel_tenant'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.company_name} ({self.subdomain})"

    @property
    def url(self):
        from django.conf import settings
        return f"https://{self.subdomain}.{settings.BASE_DOMAIN}"

    @property
    def database_url(self):
        return f"postgresql://{self.db_user}:{self.db_password}@{self.db_host}:{self.db_port}/{self.db_name}"

class TenantUser(models.Model):
    ROLE_CHOICES = [
        ('owner', 'Propietario'),
        ('admin', 'Administrador'),
        ('user', 'Usuario'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, related_name='users')
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name='tenant_memberships')
    role = models.CharField(max_length=20, choices=ROLE_CHOICES, default='user')
    is_active = models.BooleanField(default=True)
    joined_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'panel_tenant_user'
        unique_together = ['tenant', 'user']

    def __str__(self):
        return f"{self.user.username} - {self.tenant.name} ({self.role})"

class ActivityLog(models.Model):
    ACTION_CHOICES = [
        ('create', 'Creación'),
        ('update', 'Actualización'),
        ('delete', 'Eliminación'),
        ('suspend', 'Suspensión'),
        ('activate', 'Activación'),
        ('login', 'Inicio de sesión'),
        ('deploy', 'Despliegue'),
    ]

    tenant = models.ForeignKey(Tenant, on_delete=models.CASCADE, null=True, blank=True)
    user = models.ForeignKey(User, on_delete=models.SET_NULL, null=True, blank=True)
    action = models.CharField(max_length=20, choices=ACTION_CHOICES)
    description = models.TextField()
    ip_address = models.GenericIPAddressField(null=True, blank=True)
    created_at = models.DateTimeField(auto_now_add=True)

    class Meta:
        db_table = 'panel_activity_log'
        ordering = ['-created_at']

    def __str__(self):
        return f"{self.action} - {self.created_at}"
