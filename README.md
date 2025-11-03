# 🚀 TENANT MASTER - Sistema de Administración Multi-Tenant

Sistema completo de administración para gestionar múltiples productos SaaS con arquitectura híbrida (Shared + Dedicated containers).

## 📋 Características

- ✅ **Arquitectura Híbrida**: Contenedores compartidos y dedicados
- ✅ **Multi-Tenant**: Una base de datos por cliente
- ✅ **Multi-Producto**: Inventario, ERP, Shop, Landing Pages
- ✅ **Migración de Planes**: Cambio automático entre Shared ↔ Dedicated
- ✅ **Panel Admin Moderno**: 100% Responsive con Tailwind CSS
- ✅ **PostgreSQL 16**: Base de datos robusta
- ✅ **Docker**: Despliegue fácil y escalable

## 🎨 Stack Tecnológico

- **Backend**: Django 5.0
- **Frontend**: Tailwind CSS 3.4
- **Base de Datos**: PostgreSQL 16
- **Servidor**: Gunicorn
- **Containerización**: Docker + Docker Compose

## 📦 Estructura del Proyecto

```
tenant-master/
├── backend/
│   ├── config/              # Configuración Django
│   ├── accounts/            # App principal
│   │   ├── models.py        # Modelos (Product, Workspace, etc)
│   │   ├── views.py         # Vistas
│   │   ├── utils.py         # Utilidades (deploy, migrate, etc)
│   │   └── templates/       # Templates HTML
│   ├── manage.py
│   └── requirements.txt
├── Dockerfile
├── docker-compose.yml
├── .env
└── README.md
```

## 🚀 Instalación Rápida

### 1. Clonar y Configurar

```bash
# En tu VPS
cd /opt/proyectos/
git clone [tu-repo] tenant-master
cd tenant-master

# Copiar .env de ejemplo
cp .env.example .env
nano .env  # Editar variables
```

### 2. Construir y Levantar

```bash
docker-compose up -d --build
```

### 3. Inicializar Base de Datos

```bash
# Crear superusuario
docker exec -it tenant-master python manage.py createsuperuser

# Inicializar productos
docker exec -it tenant-master python manage.py shell < backend/init_products.py
```

### 4. Acceder

- **Panel Admin**: http://tu-vps:8001
- **Login**: usa el superusuario creado

## 🔧 Comandos Útiles

```bash
# Ver logs
docker logs -f tenant-master

# Reiniciar
docker-compose restart

# Ver estado
docker-compose ps

# Ejecutar migraciones
docker exec -it tenant-master python manage.py migrate

# Shell Django
docker exec -it tenant-master python manage.py shell
```

## 📊 Arquitectura

### Contenedores Compartidos (Shared)
- Planes: Free, Starter, Business
- Múltiples clientes en un solo contenedor
- Separación por base de datos

### Contenedores Dedicados (Dedicated)
- Planes: Enterprise, Lifetime
- Un contenedor por cliente
- Recursos aislados

### Puertos Asignados

```
8001 - Tenant Master (Panel Admin)
8100 - Inventario System (Shared)
8101-8150 - Inventario (Dedicated)
8200 - ERP System (Shared)
8201-8250 - ERP (Dedicated)
8300 - Shop System (Shared)
8301-8350 - Shop (Dedicated)
8400 - Landing Builder (Shared)
8401-8450 - Landing (Dedicated)
```

## 🎯 Flujo de Trabajo

### Crear Nuevo Cliente

1. Ir a **Espacios de trabajo** → **+ Nuevo workspace**
2. Llenar datos:
   - Nombre comercial
   - Subdominio
   - Producto (Inventario, ERP, etc)
   - Plan (Free, Starter, Business, Enterprise, Lifetime)
3. El sistema automáticamente:
   - Crea base de datos PostgreSQL
   - Asigna contenedor (shared o dedicated según plan)
   - Configura subdominio
   - Aplica migraciones

### Cambiar Plan de Cliente

1. Seleccionar workspace
2. Click en **Cambiar plan**
3. Elegir nuevo plan
4. Si requiere migración (Shared ↔ Dedicated):
   - El sistema automáticamente clona/elimina stack
   - Mantiene la misma base de datos
   - Reconfigura enrutamiento

## 🗄️ Base de Datos

### Tenant Master (tenant_master)
Base de datos principal que contiene:
- Productos disponibles
- Workspaces de clientes
- Usuarios y membresías
- Logs de actividad
- Historial de cambios de plan

### Bases de Datos de Clientes
Cada cliente tiene su propia base de datos:
- `inventario_[slug]`
- `erp_[slug]`
- `shop_[slug]`
- `landing_[slug]`

## 🔐 Seguridad

- ✅ Passwords seguros autogenerados
- ✅ Separación de bases de datos
- ✅ Variables de entorno para secrets
- ✅ ALLOWED_HOSTS configurado
- ✅ CORS configurado

## 📱 Responsive Design

El panel admin es 100% responsive:
- **Mobile**: < 640px
- **Tablet**: 640px - 1024px
- **Desktop**: > 1024px

## 🐛 Troubleshooting

### Error: "column does not exist"
```bash
# Aplicar migraciones
docker exec -it tenant-master python manage.py migrate
```

### PostgreSQL no conecta
```bash
# Verificar que postgres está corriendo
docker ps | grep postgres

# Ver logs
docker logs postgres16
```

### Puerto ya en uso
```bash
# Ver qué usa el puerto
sudo lsof -i :8001

# Cambiar puerto en docker-compose.yml
```

## 📞 Soporte

Para problemas o dudas:
1. Revisar logs: `docker logs tenant-master`
2. Ver documentación de Django
3. Revisar issues en GitHub

## 📄 Licencia

Propietario - Todos los derechos reservados

---

**Desarrollado con ❤️ por kitagli.com**
