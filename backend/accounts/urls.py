from django.urls import path
from django.contrib.auth import views as auth_views
from . import views

urlpatterns = [
    # Autenticación
    path('', views.dashboard, name='dashboard'),
    path('register/', views.register, name='register'),
    path('login/', auth_views.LoginView.as_view(template_name='accounts/login.html'), name='login'),
    path('logout/', views.user_logout, name='logout'),
    
    # Workspaces de usuario
    path('workspace/<int:workspace_id>/ready/', views.workspace_ready, name='workspace_ready'),
    
    # Panel Administrativo
    path('admin/dashboard/', views.admin_dashboard, name='admin_dashboard'),
    path('admin/workspace/<int:workspace_id>/', views.admin_workspace_detail, name='admin_workspace_detail'),
    path('admin/workspace/<int:workspace_id>/<str:action>/', views.admin_workspace_action, name='admin_workspace_action'),
    path('admin/databases/', views.admin_database_manager, name='admin_database_manager'),
    path('admin/activity/', views.admin_activity_log, name='admin_activity_log'),
    path('admin/products/', views.admin_products, name='admin_products'),
]
