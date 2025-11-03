from django.contrib import admin
from .models import Product, Workspace, WorkspaceMembership, DatabaseBackup, ActivityLog, PlanChange


@admin.register(Product)
class ProductAdmin(admin.ModelAdmin):
    list_display = ['name', 'display_name', 'subdomain_prefix', 'shared_container_port', 'deployment_range', 'version', 'is_active', 'workspace_count']
    list_filter = ['is_active', 'created_at']
    search_fields = ['name', 'display_name', 'subdomain_prefix']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('name', 'display_name', 'subdomain_prefix', 'icon', 'description', 'version', 'is_active')
        }),
        ('Contenedor Compartido', {
            'fields': ('shared_container_name', 'shared_container_port', 'stack_path', 'docker_image')
        }),
        ('Contenedores Dedicados', {
            'fields': ('dedicated_port_start', 'dedicated_port_end'),
            'description': 'Rango de puertos para contenedores dedicados (Enterprise/Lifetime)'
        }),
        ('Legacy', {
            'fields': ('container_port',),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('created_at',)
        }),
    )
    
    def workspace_count(self, obj):
        return obj.workspaces.count()
    workspace_count.short_description = 'Workspaces'
    
    def deployment_range(self, obj):
        return f"{obj.dedicated_port_start}-{obj.dedicated_port_end}"
    deployment_range.short_description = 'Rango Dedicados'


@admin.register(Workspace)
class WorkspaceAdmin(admin.ModelAdmin):
    list_display = ['company_name', 'subdomain', 'product', 'plan_type', 'deployment_type', 'status', 'db_size_mb', 'created_at']
    list_filter = ['status', 'plan_type', 'deployment_type', 'product', 'created_at']
    search_fields = ['company_name', 'subdomain', 'db_name']
    readonly_fields = ['created_at', 'updated_at', 'db_created', 'plan_changed_at', 'plan_changed_by']
    
    fieldsets = (
        ('Información Básica', {
            'fields': ('product', 'company_name', 'subdomain')
        }),
        ('Plan y Deployment', {
            'fields': ('plan_type', 'deployment_type', 'status', 'is_active'),
            'description': 'Enterprise y Lifetime usan contenedores dedicados'
        }),
        ('Historial de Plan', {
            'fields': ('previous_plan', 'plan_changed_at', 'plan_changed_by'),
            'classes': ('collapse',)
        }),
        ('Base de Datos', {
            'fields': ('db_name', 'db_user', 'db_password', 'db_host', 'db_port', 'db_created', 'db_size_mb')
        }),
        ('Contenedor Docker', {
            'fields': ('container_name', 'container_port', 'container_id', 'container_status', 'stack_path'),
            'classes': ('collapse',)
        }),
        ('Fechas', {
            'fields': ('created_at', 'updated_at', 'paused_at', 'subscription_end')
        }),
        ('Notas', {
            'fields': ('admin_notes',),
            'classes': ('collapse',)
        }),
    )


@admin.register(WorkspaceMembership)
class WorkspaceMembershipAdmin(admin.ModelAdmin):
    list_display = ['user', 'workspace', 'role', 'is_active', 'joined_at']
    list_filter = ['role', 'is_active', 'joined_at']
    search_fields = ['user__username', 'workspace__company_name']
    readonly_fields = ['joined_at']


@admin.register(DatabaseBackup)
class DatabaseBackupAdmin(admin.ModelAdmin):
    list_display = ['workspace', 'filename', 'size_mb', 'backup_type', 'created_by', 'created_at']
    list_filter = ['backup_type', 'created_at']
    search_fields = ['workspace__company_name', 'filename']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Información', {
            'fields': ('workspace', 'filename', 'file_path', 'size_mb')
        }),
        ('Detalles', {
            'fields': ('backup_type', 'created_by', 'created_at', 'notes')
        }),
    )


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ['action', 'user', 'workspace', 'created_at', 'ip_address']
    list_filter = ['action', 'created_at']
    search_fields = ['user__username', 'workspace__company_name', 'description']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Acción', {
            'fields': ('action', 'description')
        }),
        ('Contexto', {
            'fields': ('user', 'workspace', 'ip_address', 'created_at')
        }),
    )
    
    def has_add_permission(self, request):
        return False
    
    def has_change_permission(self, request, obj=None):
        return False


@admin.register(PlanChange)
class PlanChangeAdmin(admin.ModelAdmin):
    list_display = ['workspace', 'old_plan', 'new_plan', 'deployment_change', 'migration_required', 'changed_by', 'created_at']
    list_filter = ['migration_required', 'migration_success', 'old_plan', 'new_plan', 'created_at']
    search_fields = ['workspace__company_name', 'reason']
    readonly_fields = ['created_at']
    
    fieldsets = (
        ('Workspace', {
            'fields': ('workspace', 'changed_by', 'created_at')
        }),
        ('Cambio de Plan', {
            'fields': ('old_plan', 'new_plan', 'reason')
        }),
        ('Deployment', {
            'fields': ('old_deployment', 'new_deployment', 'migration_required', 'migration_success', 'migration_notes')
        }),
    )
    
    def deployment_change(self, obj):
        arrow = "→"
        if obj.old_deployment == obj.new_deployment:
            return f"{obj.old_deployment}"
        return f"{obj.old_deployment} {arrow} {obj.new_deployment}"
    deployment_change.short_description = 'Deployment'
    
    def has_add_permission(self, request):
        return False
