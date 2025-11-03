# Sistema de Gestión de Tenants - Tenant Master

## 📋 Resumen del Sistema

Este es un **sistema completo de gestión de tenants multi-inquilino** que te permite administrar todos tus clientes, sus bases de datos y aplicaciones desde una interfaz web, **sin necesidad de usar comandos Linux**.

## 🎯 Características Principales

### 1. **Panel Administrativo Completo**
- Vista general de todos los workspaces/tenants
- Estadísticas en tiempo real
- Filtros avanzados por producto, plan y estado
- Dashboard con métricas clave

### 2. **Gestión de Bases de Datos**
- ✅ Crear bases de datos PostgreSQL automáticamente
- ✅ Eliminar bases de datos de forma segura
- ✅ Crear backups manuales y automáticos
- ✅ Restaurar desde backups
- ✅ Ver tamaño de cada base de datos
- ✅ Ejecutar VACUUM para optimización
- ✅ Ver número de conexiones activas

### 3. **Gestión de Workspaces**
- Crear, pausar, reanudar y eliminar workspaces
- Cambiar planes de suscripción
- Ver expiración de suscripciones
- Notas administrativas por workspace
- Gestión de miembros y roles

### 4. **Monitoreo y Logs**
- Registro completo de todas las acciones administrativas
- Historial de cambios por workspace
- Seguimiento de quién hizo qué y cuándo
- Registro de direcciones IP

### 5. **Gestión de Productos**
- Múltiples productos (Inventario, ERP, E-commerce, etc.)
- Cada producto con su propia configuración
- Subdominios personalizados por producto

## 📁 Archivos Modificados/Creados

### Modelos (`accounts/models.py`)
- ✅ `Product` - Productos disponibles
- ✅ `Workspace` - Espacios de trabajo (tenants)
- ✅ `WorkspaceMembership` - Membresías de usuarios
- ✅ `DatabaseBackup` - Registro de backups
- ✅ `ActivityLog` - Logs de actividad

### Vistas (`accounts/views.py`)
**Vistas de Usuario:**
- `register` - Registro de nuevos usuarios
- `dashboard` - Dashboard del usuario
- `workspace_ready` - Confirmación de workspace creado
- `user_logout` - Cerrar sesión

**Vistas Administrativas:**
- `admin_dashboard` - Dashboard principal del admin
- `admin_workspace_detail` - Detalles de un workspace
- `admin_workspace_action` - Acciones sobre workspaces
- `admin_database_manager` - Gestor de bases de datos
- `admin_activity_log` - Registro de actividades
- `admin_products` - Gestión de productos

### Utilidades (`accounts/utils.py`)
Funciones para gestión de bases de datos:
- `create_tenant_database()` - Crear BD y usuario
- `delete_tenant_database()` - Eliminar BD y usuario
- `backup_tenant_database()` - Crear backup
- `restore_tenant_database()` - Restaurar backup
- `get_database_size()` - Obtener tamaño de BD
- `list_database_tables()` - Listar tablas
- `get_database_connections()` - Ver conexiones activas
- `check_postgres_connection()` - Verificar conexión a PostgreSQL
- `vacuum_database()` - Optimizar BD

### Admin Django (`accounts/admin.py`)
- Panel de administración de Django mejorado
- Registro de todos los modelos
- Filtros y búsquedas avanzadas
- Solo lectura para logs de actividad

## 🔧 Próximos Pasos

### 1. Aplicar Migraciones
```bash
cd C:\Proyectos_vps\tenant_master\backend
python manage.py makemigrations
python manage.py migrate
```

### 2. Crear Superusuario
```bash
python manage.py createsuperuser
```

### 3. Crear Productos Iniciales
Accede al admin de Django (`/admin/`) y crea los productos:
- **Inventario**: subdomain_prefix=`inv`, puerto=8001
- **ERP**: subdomain_prefix=`erp`, puerto=8002  
- **E-commerce**: subdomain_prefix=`shop`, puerto=8003
- **Website Builder**: subdomain_prefix=`web`, puerto=8004

### 4. Acceder al Panel Admin
- URL: `http://tu-dominio/admin/dashboard/`
- Solo usuarios con `is_staff=True` pueden acceder

## 📊 Estructura del Panel Administrativo

### Dashboard Principal
- **Estadísticas generales**: Total de workspaces, activos, pausados
- **Tamaño total de BDs**: Suma de todas las bases de datos
- **Distribución por producto**: Gráficos y contadores
- **Distribución por plan**: Free, Starter, Business, Enterprise, Lifetime
- **Próximos a expirar**: Workspaces con suscripción por vencer
- **Actividad reciente**: Últimas acciones administrativas

### Gestor de Bases de Datos
- Lista de todas las bases de datos
- Tamaño de cada BD
- Botones para:
  - 🔄 Sincronizar tamaño
  - 💾 Crear backup
  - 🗑️ Eliminar BD
  - 🔧 Ejecutar VACUUM
  - 👁️ Ver detalles

### Detalle de Workspace
- Información completa del workspace
- Credenciales de la base de datos
- Miembros y roles
- Historial de backups
- Log de actividad del workspace
- Acciones rápidas:
  - ⏸️ Pausar
  - ▶️ Reanudar
  - 🚫 Suspender
  - 💾 Backup
  - 🗑️ Eliminar

### Log de Actividad
- Registro completo de acciones
- Filtros por:
  - Tipo de acción
  - Usuario
  - Workspace
  - Fecha
- Información de IP

## 🎨 Filtros Disponibles

### En Dashboard Admin
1. **Por Producto**: Inventario, ERP, Shop, Website
2. **Por Plan**: free, starter, business, enterprise, lifetime
3. **Por Estado**: active, paused, suspended, cancelled
4. **Búsqueda**: Nombre de empresa, subdominio, nombre de BD

## 🔐 Seguridad

- Solo usuarios con `is_staff=True` acceden al panel admin
- Todas las contraseñas de BD se generan de forma segura (24 caracteres)
- Log completo de todas las acciones administrativas
- Registro de IPs en el log de actividad

## 🚀 Características Avanzadas

### Planes de Suscripción
- **Free**: Plan gratuito
- **Starter**: Plan inicial
- **Business**: Plan de negocios
- **Enterprise**: Plan empresarial
- **Lifetime**: Compra vitalicia (sin expiración)

### Estados de Workspace
- **active**: Activo y funcionando
- **paused**: Pausado temporalmente
- **suspended**: Suspendido (por falta de pago, etc.)
- **cancelled**: Cancelado permanentemente

### Roles de Usuario en Workspace
- **owner**: Propietario (control total)
- **admin**: Administrador (casi todo el control)
- **member**: Miembro (acceso básico)
- **viewer**: Visualizador (solo lectura)

## 📝 Notas Importantes

1. **Backups**: Se guardan en `/backups/` por defecto
2. **Credenciales BD**: Se guardan encriptadas en el workspace
3. **Logs**: Se mantienen indefinidamente (configurar limpieza automática si es necesario)
4. **Conexión PostgreSQL**: Se usa la configuración del `settings.py`

## 🔄 Flujo de Creación de Tenant

1. Usuario se registra en `/register/`
2. Sistema crea:
   - Usuario en Django
   - Base de datos PostgreSQL
   - Usuario de BD con permisos
   - Workspace en la BD maestra
   - Membresía del usuario como owner
3. Log de la creación
4. Usuario es redirigido a la confirmación
5. Admin puede ver el nuevo workspace en el panel

## 💡 Ventajas del Sistema

✅ **Sin SSH**: Todo desde la interfaz web
✅ **Seguro**: Contraseñas generadas automáticamente
✅ **Escalable**: Soporta múltiples productos
✅ **Auditable**: Log completo de acciones
✅ **Flexible**: Múltiples planes y estados
✅ **Profesional**: Interfaz moderna con Tailwind CSS

## 🛠️ Comandos Útiles

```bash
# Aplicar migraciones
python manage.py makemigrations
python manage.py migrate

# Crear superusuario
python manage.py createsuperuser

# Correr servidor
python manage.py runserver

# Colectar archivos estáticos
python manage.py collectstatic
```

## 📌 TODO - Próximas Mejoras

1. ⏺️ Crear plantillas HTML del panel admin
2. ⏺️ Implementar gestión de contenedores Docker
3. ⏺️ Sistema de notificaciones por email
4. ⏺️ Backups automáticos programados
5. ⏺️ Gráficos de uso de recursos
6. ⏺️ Exportación de reports en PDF/Excel
7. ⏺️ API REST para automatización
8. ⏺️ Webhooks para eventos
9. ⏺️ Integración con Stripe para pagos
10. ⏺️ Dashboard de métricas por workspace

## 📞 Soporte

Para cualquier duda o mejora, todo el código está documentado y listo para ser extendido.
