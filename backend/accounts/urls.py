"""
URL configuration for accounts app
"""
from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Autenticación
    path('', views.index, name='index'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Dashboard usuario
    path('dashboard/', views.dashboard, name='dashboard'),
    
    # Panel Admin
    path('admin/panel/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/workspaces/', views.admin_workspaces, name='admin_workspaces'),
    path('admin/workspaces/create/', views.admin_create_workspace, name='admin_create_workspace'),
    path('admin/workspaces/<int:workspace_id>/', views.admin_workspace_detail, name='admin_workspace_detail'),
    path('admin/workspaces/<int:workspace_id>/change-plan/', views.admin_change_plan, name='admin_change_plan'),
    path('admin/workspaces/<int:workspace_id>/action/<str:action>/', views.admin_workspace_action, name='admin_workspace_action'),
    
    # Otras secciones del admin
    path('admin/clients/', views.admin_clients, name='admin_clients'),
    path('admin/deployments/', views.admin_deployments, name='admin_deployments'),
    path('admin/products/', views.admin_products, name='admin_products'),
    path('admin/migrations/', views.admin_migrations, name='admin_migrations'),
    path('admin/databases/', views.admin_databases, name='admin_databases'),
    path('admin/settings/', views.admin_settings, name='admin_settings'),
]
