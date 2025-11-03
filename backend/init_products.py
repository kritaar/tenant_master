"""
Script para inicializar productos con configuración híbrida
Ejecutar con: python manage.py shell < init_products.py
"""

from accounts.models import Product

print("🚀 Inicializando productos con arquitectura híbrida...")

products_data = [
    {
        'name': 'inventario',
        'display_name': 'Sistema de Inventario',
        'subdomain_prefix': 'inv',
        'icon': '📦',
        'description': 'Sistema completo de gestión de inventarios, control de stock, entradas y salidas.',
        
        # Contenedor compartido
        'shared_container_name': 'inventario-system',
        'shared_container_port': 8100,
        'stack_path': '/opt/stacks/inventario-system',
        
        # Contenedores dedicados
        'dedicated_port_start': 8101,
        'dedicated_port_end': 8150,
        
        # Configuración Docker
        'docker_image': 'kitagli/inventario:latest',
        'container_port': 8100,  # Legacy
        'version': '1.0.0',
    },
    {
        'name': 'erp',
        'display_name': 'Sistema ERP',
        'subdomain_prefix': 'erp',
        'icon': '💼',
        'description': 'ERP empresarial con módulos de ventas, compras, contabilidad y reportes.',
        
        # Contenedor compartido
        'shared_container_name': 'erp-system',
        'shared_container_port': 8200,
        'stack_path': '/opt/stacks/erp-system',
        
        # Contenedores dedicados
        'dedicated_port_start': 8201,
        'dedicated_port_end': 8250,
        
        # Configuración Docker
        'docker_image': 'kitagli/erp:latest',
        'container_port': 8200,  # Legacy
        'version': '1.0.0',
    },
    {
        'name': 'shop',
        'display_name': 'Tienda E-commerce',
        'subdomain_prefix': 'shop',
        'icon': '🛒',
        'description': 'Plataforma completa de e-commerce con carrito, pagos y gestión de productos.',
        
        # Contenedor compartido
        'shared_container_name': 'shop-system',
        'shared_container_port': 8300,
        'stack_path': '/opt/stacks/shop-system',
        
        # Contenedores dedicados
        'dedicated_port_start': 8301,
        'dedicated_port_end': 8350,
        
        # Configuración Docker
        'docker_image': 'kitagli/shop:latest',
        'container_port': 8300,  # Legacy
        'version': '1.0.0',
    },
    {
        'name': 'landing',
        'display_name': 'Constructor de Landing Pages',
        'subdomain_prefix': 'web',
        'icon': '🌐',
        'description': 'Constructor drag & drop para crear landing pages profesionales sin código.',
        
        # Contenedor compartido
        'shared_container_name': 'landing-builder',
        'shared_container_port': 8400,
        'stack_path': '/opt/stacks/landing-builder',
        
        # Contenedores dedicados
        'dedicated_port_start': 8401,
        'dedicated_port_end': 8450,
        
        # Configuración Docker
        'docker_image': 'kitagli/landing:latest',
        'container_port': 8400,  # Legacy
        'version': '1.0.0',
    },
]

created = 0
updated = 0

for product_data in products_data:
    product, was_created = Product.objects.update_or_create(
        name=product_data['name'],
        defaults=product_data
    )
    
    if was_created:
        created += 1
        print(f"✅ Producto creado: {product.display_name}")
        print(f"   Shared: {product.shared_container_name}:{product.shared_container_port}")
        print(f"   Dedicated: Puertos {product.dedicated_port_start}-{product.dedicated_port_end}")
    else:
        updated += 1
        print(f"🔄 Producto actualizado: {product.display_name}")

print(f"\n📊 Resumen:")
print(f"   Creados: {created}")
print(f"   Actualizados: {updated}")
print(f"   Total: {Product.objects.count()}")
print("\n✨ ¡Productos inicializados correctamente!")

# Mostrar configuración de puertos
print("\n🔌 Configuración de puertos:")
for product in Product.objects.all():
    print(f"\n{product.icon} {product.display_name}")
    print(f"   Shared:    {product.shared_container_port}")
    print(f"   Dedicated: {product.dedicated_port_start}-{product.dedicated_port_end}")
