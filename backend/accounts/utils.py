"""
Utilidades para gestión de bases de datos y tenants
"""
import psycopg2
from psycopg2.extensions import ISOLATION_LEVEL_AUTOCOMMIT
from django.conf import settings
import logging
import subprocess
import os
from datetime import datetime
from .models import generate_password

logger = logging.getLogger(__name__)


def get_postgres_connection():
    """Obtener conexión a PostgreSQL como superusuario"""
    return psycopg2.connect(
        dbname='postgres',
        user=settings.DATABASES['default']['USER'],
        password=settings.DATABASES['default']['PASSWORD'],
        host=settings.DATABASES['default']['HOST'],
        port=settings.DATABASES['default']['PORT']
    )


def create_tenant_database(product_name, subdomain, company_name):
    """
    Crear base de datos, usuario y permisos para un tenant
    
    Returns:
        dict: Credenciales de la BD creada
    """
    # Generar nombres únicos
    db_name = f"{product_name}_{subdomain}".lower().replace('-', '_')
    db_user = f"user_{db_name}"
    db_password = generate_password()
    
    try:
        # Conectar como superusuario
        conn = get_postgres_connection()
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        logger.info(f"Creando base de datos: {db_name}")
        
        # 1. Crear usuario
        cursor.execute(f"""
            CREATE USER {db_user} WITH PASSWORD %s;
        """, (db_password,))
        logger.info(f"Usuario creado: {db_user}")
        
        # 2. Crear base de datos
        cursor.execute(f"""
            CREATE DATABASE {db_name} 
            OWNER {db_user}
            ENCODING 'UTF8'
            LC_COLLATE = 'en_US.UTF-8'
            LC_CTYPE = 'en_US.UTF-8';
        """)
        logger.info(f"Base de datos creada: {db_name}")
        
        # 3. Otorgar permisos
        cursor.execute(f"""
            GRANT ALL PRIVILEGES ON DATABASE {db_name} TO {db_user};
        """)
        
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Tenant creado exitosamente: {db_name}")
        
        return {
            'db_name': db_name,
            'db_user': db_user,
            'db_password': db_password,
            'db_host': settings.DATABASES['default']['HOST'],
            'db_port': settings.DATABASES['default']['PORT'],
        }
        
    except psycopg2.Error as e:
        logger.error(f"❌ Error creando tenant: {e}")
        raise Exception(f"Error al crear la base de datos: {str(e)}")


def delete_tenant_database(db_name):
    """
    Eliminar base de datos y usuario de un tenant
    """
    db_user = f"user_{db_name}"
    
    try:
        conn = get_postgres_connection()
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        logger.info(f"Eliminando base de datos: {db_name}")
        
        # 1. Terminar conexiones activas
        cursor.execute(f"""
            SELECT pg_terminate_backend(pg_stat_activity.pid)
            FROM pg_stat_activity
            WHERE pg_stat_activity.datname = '{db_name}'
            AND pid <> pg_backend_pid();
        """)
        
        # 2. Eliminar base de datos
        cursor.execute(f"DROP DATABASE IF EXISTS {db_name};")
        logger.info(f"Base de datos eliminada: {db_name}")
        
        # 3. Eliminar usuario
        cursor.execute(f"DROP USER IF EXISTS {db_user};")
        logger.info(f"Usuario eliminado: {db_user}")
        
        cursor.close()
        conn.close()
        
        logger.info(f"✅ Tenant eliminado exitosamente: {db_name}")
        return True
        
    except psycopg2.Error as e:
        logger.error(f"❌ Error eliminando tenant: {e}")
        raise Exception(f"Error al eliminar la base de datos: {str(e)}")


def backup_tenant_database(db_name, backup_dir='/backups'):
    """
    Crear backup de una base de datos tenant
    
    Args:
        db_name: Nombre de la base de datos
        backup_dir: Directorio donde guardar el backup
    
    Returns:
        str: Ruta completa del archivo de backup
    """
    try:
        # Crear directorio de backups si no existe
        os.makedirs(backup_dir, exist_ok=True)
        
        # Generar nombre del archivo
        timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
        backup_file = f"{db_name}_{timestamp}.sql.gz"
        backup_path = os.path.join(backup_dir, backup_file)
        
        logger.info(f"Creando backup: {backup_path}")
        
        # Comando pg_dump con compresión
        cmd = [
            'pg_dump',
            '-h', settings.DATABASES['default']['HOST'],
            '-p', str(settings.DATABASES['default']['PORT']),
            '-U', settings.DATABASES['default']['USER'],
            '-d', db_name,
            '--no-password',
            '-F', 'c',  # Custom format
            '-f', backup_path
        ]
        
        # Configurar variable de entorno para la contraseña
        env = os.environ.copy()
        env['PGPASSWORD'] = settings.DATABASES['default']['PASSWORD']
        
        # Ejecutar comando
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"✅ Backup creado exitosamente: {backup_path}")
        return backup_path
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error creando backup: {e.stderr}")
        raise Exception(f"Error al crear backup: {e.stderr}")
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        raise


def restore_tenant_database(db_name, backup_path):
    """
    Restaurar base de datos desde un backup
    
    Args:
        db_name: Nombre de la base de datos
        backup_path: Ruta completa del archivo de backup
    """
    try:
        logger.info(f"Restaurando backup: {backup_path} -> {db_name}")
        
        # Comando pg_restore
        cmd = [
            'pg_restore',
            '-h', settings.DATABASES['default']['HOST'],
            '-p', str(settings.DATABASES['default']['PORT']),
            '-U', settings.DATABASES['default']['USER'],
            '-d', db_name,
            '--no-password',
            '-c',  # Clean (drop) database objects before recreating
            backup_path
        ]
        
        # Configurar variable de entorno para la contraseña
        env = os.environ.copy()
        env['PGPASSWORD'] = settings.DATABASES['default']['PASSWORD']
        
        # Ejecutar comando
        result = subprocess.run(
            cmd,
            env=env,
            capture_output=True,
            text=True,
            check=True
        )
        
        logger.info(f"✅ Backup restaurado exitosamente en: {db_name}")
        return True
        
    except subprocess.CalledProcessError as e:
        logger.error(f"❌ Error restaurando backup: {e.stderr}")
        raise Exception(f"Error al restaurar backup: {e.stderr}")
    except Exception as e:
        logger.error(f"❌ Error inesperado: {e}")
        raise


def get_database_size(db_name):
    """
    Obtener el tamaño de una base de datos en MB
    
    Args:
        db_name: Nombre de la base de datos
    
    Returns:
        float: Tamaño en MB
    """
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT pg_database_size('{db_name}') / 1024.0 / 1024.0 as size_mb;
        """)
        
        result = cursor.fetchone()
        size_mb = result[0] if result else 0.0
        
        cursor.close()
        conn.close()
        
        return round(size_mb, 2)
        
    except psycopg2.Error as e:
        logger.error(f"❌ Error obteniendo tamaño de BD: {e}")
        return 0.0


def list_database_tables(db_name):
    """
    Listar todas las tablas de una base de datos
    
    Args:
        db_name: Nombre de la base de datos
    
    Returns:
        list: Lista de nombres de tablas
    """
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        cursor = conn.cursor()
        
        cursor.execute("""
            SELECT tablename 
            FROM pg_catalog.pg_tables 
            WHERE schemaname = 'public'
            ORDER BY tablename;
        """)
        
        tables = [row[0] for row in cursor.fetchall()]
        
        cursor.close()
        conn.close()
        
        return tables
        
    except psycopg2.Error as e:
        logger.error(f"❌ Error listando tablas: {e}")
        return []


def get_database_connections(db_name):
    """
    Obtener número de conexiones activas a una base de datos
    
    Args:
        db_name: Nombre de la base de datos
    
    Returns:
        int: Número de conexiones activas
    """
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        
        cursor.execute(f"""
            SELECT count(*) 
            FROM pg_stat_activity 
            WHERE datname = '{db_name}';
        """)
        
        result = cursor.fetchone()
        connections = result[0] if result else 0
        
        cursor.close()
        conn.close()
        
        return connections
        
    except psycopg2.Error as e:
        logger.error(f"❌ Error obteniendo conexiones: {e}")
        return 0


def check_postgres_connection():
    """
    Verificar si se puede conectar a PostgreSQL
    
    Returns:
        dict: Estado de la conexión
    """
    try:
        conn = get_postgres_connection()
        cursor = conn.cursor()
        
        # Obtener versión de PostgreSQL
        cursor.execute("SELECT version();")
        version = cursor.fetchone()[0]
        
        # Obtener número total de bases de datos
        cursor.execute("SELECT count(*) FROM pg_database WHERE datistemplate = false;")
        total_databases = cursor.fetchone()[0]
        
        cursor.close()
        conn.close()
        
        return {
            'status': 'connected',
            'version': version,
            'total_databases': total_databases,
            'host': settings.DATABASES['default']['HOST'],
            'port': settings.DATABASES['default']['PORT'],
        }
        
    except Exception as e:
        logger.error(f"❌ Error conectando a PostgreSQL: {e}")
        return {
            'status': 'error',
            'error': str(e),
            'host': settings.DATABASES['default']['HOST'],
            'port': settings.DATABASES['default']['PORT'],
        }


def vacuum_database(db_name):
    """
    Ejecutar VACUUM en una base de datos para recuperar espacio
    
    Args:
        db_name: Nombre de la base de datos
    
    Returns:
        bool: True si se ejecutó exitosamente
    """
    try:
        conn = psycopg2.connect(
            dbname=db_name,
            user=settings.DATABASES['default']['USER'],
            password=settings.DATABASES['default']['PASSWORD'],
            host=settings.DATABASES['default']['HOST'],
            port=settings.DATABASES['default']['PORT']
        )
        conn.set_isolation_level(ISOLATION_LEVEL_AUTOCOMMIT)
        cursor = conn.cursor()
        
        logger.info(f"Ejecutando VACUUM en: {db_name}")
        cursor.execute("VACUUM ANALYZE;")
        
        cursor.close()
        conn.close()
        
        logger.info(f"✅ VACUUM completado en: {db_name}")
        return True
        
    except psycopg2.Error as e:
        logger.error(f"❌ Error ejecutando VACUUM: {e}")
        return False
