# 🎯 PASO 1 COMPLETADO: MODELOS ACTUALIZADOS

## ✅ Archivos Modificados:

1. **accounts/models.py** - Modelos actualizados con:
   - Campo `deployment_type` en Workspace
   - Campos de contenedor compartido en Product
   - Rango de puertos dedicados en Product
   - Historial de cambios de plan
   - Nuevo modelo `PlanChange`
   - Métodos helper: `can_upgrade()`, `can_downgrade()`, `requires_migration()`

2. **accounts/admin.py** - Admin actualizado con:
   - Registro de PlanChange
   - Campos nuevos en Product y Workspace
   - Mejor visualización

3. **init_products.py** - Script de inicialización con configuración híbrida

---

## 🚀 PRÓXIMOS PASOS:

### 1. Crear y Aplicar Migraciones

```bash
# En tu VPS o local (donde tengas la BD)
cd /opt/proyectos/tenant-master/backend
# o en Windows: cd C:\Proyectos_vps\tenant_master\backend

# Crear migraciones
python manage.py makemigrations accounts

# Ver SQL que se ejecutará (opcional)
python manage.py sqlmigrate accounts 0XXX

# Aplicar migraciones
python manage.py migrate accounts
```

### 2. Inicializar Productos

```bash
# Ejecutar script de inicialización
python manage.py shell < init_products.py
```

---

## 📊 CAMBIOS EN LA BASE DE DATOS

### Nuevas Columnas en `accounts_product`:
```sql
shared_container_port       INT DEFAULT 8000
shared_container_name       VARCHAR(100)
stack_path                  VARCHAR(500)
dedicated_port_start        INT DEFAULT 8100
dedicated_port_end          INT DEFAULT 8199
```

### Nuevas Columnas en `accounts_workspace`:
```sql
deployment_type             VARCHAR(20) DEFAULT 'shared'
stack_path                  VARCHAR(500)
previous_plan               VARCHAR(20)
plan_changed_at             TIMESTAMP NULL
plan_changed_by_id          INT NULL (FK a auth_user)
```

### Nueva Tabla `accounts_planchange`:
```sql
id                          SERIAL PRIMARY KEY
workspace_id                INT (FK a accounts_workspace)
changed_by_id               INT (FK a auth_user)
old_plan                    VARCHAR(20)
new_plan                    VARCHAR(20)
old_deployment              VARCHAR(20)
new_deployment              VARCHAR(20)
migration_required          BOOLEAN DEFAULT FALSE
migration_success           BOOLEAN DEFAULT TRUE
migration_notes             TEXT
reason                      TEXT
created_at                  TIMESTAMP
```

---

## 🎨 ESTRUCTURA DESPUÉS DE MIGRAR

```
Products:
┌──────────────┬─────────────┬─────────────┬──────────────┐
│ Producto     │ Shared Port │ Dedicated   │ Stack Path   │
├──────────────┼─────────────┼─────────────┼──────────────┤
│ Inventario   │ 8100        │ 8101-8150   │ /opt/stacks/ │
│ ERP          │ 8200        │ 8201-8250   │ /opt/stacks/ │
│ Shop         │ 8300        │ 8301-8350   │ /opt/stacks/ │
│ Landing      │ 8400        │ 8401-8450   │ /opt/stacks/ │
└──────────────┴─────────────┴─────────────┴──────────────┘

Workspaces Existentes:
Todos los workspaces existentes tendrán:
- deployment_type = 'shared' (por defecto)
- stack_path = '' (vacío)
```

---

## ⚠️ IMPORTANTE

### Migración de Datos Existentes:

Los workspaces existentes automáticamente tendrán:
- `deployment_type = 'shared'`
- `container_port` = puerto del product
- `container_name` = nombre del contenedor compartido

**NO se requiere migración manual de datos.**

---

## 🧪 VERIFICAR LA MIGRACIÓN

Después de aplicar las migraciones, verifica:

```python
# En el shell de Django
python manage.py shell

>>> from accounts.models import Product, Workspace
>>> 
>>> # Verificar productos
>>> for p in Product.objects.all():
...     print(f"{p.name}: Shared={p.shared_container_port}, Dedicated={p.dedicated_port_start}-{p.dedicated_port_end}")
>>> 
>>> # Verificar workspaces
>>> for w in Workspace.objects.all():
...     print(f"{w.company_name}: Plan={w.plan_type}, Deployment={w.deployment_type}")
```

---

## ✅ CHECKLIST

Antes de continuar al Paso 2, verifica:

- [ ] Migraciones creadas sin errores
- [ ] Migraciones aplicadas correctamente
- [ ] Productos inicializados
- [ ] Workspaces existentes con deployment_type='shared'
- [ ] Admin de Django muestra los campos nuevos

---

## 📞 Si Hay Errores

### Error: "No such column"
```bash
# Recrear migraciones
python manage.py makemigrations accounts --empty
# Editar y aplicar
```

### Error: "Constraint failed"
```bash
# Verificar datos existentes
python manage.py dbshell
SELECT * FROM accounts_workspace;
```

---

## 🎯 SIGUIENTE: PASO 2

Una vez completado este paso, continúa con:
- **Paso 2**: Actualizar `utils.py` con funciones de deploy/undeploy
- **Paso 3**: Actualizar `views.py` con cambio de planes
- **Paso 4**: Crear templates responsive

---

**¿Listo para aplicar las migraciones?** Ejecuta los comandos arriba y avísame cuando termines. 🚀
