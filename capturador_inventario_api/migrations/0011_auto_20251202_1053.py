from django.db import migrations

def mover_datos_a_empleado(apps, schema_editor):
    # NOMBRE DE TU APP:
    # Verifica en settings.py cómo se llama la app.
    # Por defecto, basado en tus carpetas, debería ser 'capturador_inventario_api'.
    app_name = 'capturador_inventario_api'
    
    try:
        Administradores = apps.get_model(app_name, 'Administradores')
        Capturadores = apps.get_model(app_name, 'Capturadores')
        Empleado = apps.get_model(app_name, 'Empleado')
    except LookupError:
        print(f"Error: No se encontró la app '{app_name}'. Verifica el nombre en INSTALLED_APPS.")
        return

    # 1. Migrar Administradores
    # Campos disponibles en Administradores: clave_admin, telefono, fecha_nacimiento, edad, creation, update
    for admin in Administradores.objects.all():
        if not Empleado.objects.filter(user=admin.user).exists():
            Empleado.objects.create(
                user=admin.user,
                clave_interna=admin.clave_admin, 
                telefono=admin.telefono,
                fecha_nacimiento=admin.fecha_nacimiento,
                edad=admin.edad,
                puesto='ADMIN', 
                creation=admin.creation or admin.update, # Fallback por si creation es null
            )
            print(f"Migrado Admin: {admin.user.username}")

    # 2. Migrar Capturadores
    # Campos disponibles en Capturadores: id_trabajador, telefono, edad, creation, update
    # Nota: Capturadores NO tiene fecha_nacimiento en tu modelo actual.
    for cap in Capturadores.objects.all():
        if not Empleado.objects.filter(user=cap.user).exists():
            Empleado.objects.create(
                user=cap.user,
                clave_interna=cap.id_trabajador,
                telefono=cap.telefono,
                edad=cap.edad,
                fecha_nacimiento=None, # No existe en el modelo origen
                puesto='CAPTURADOR',
                creation=cap.creation or cap.update,
            )
            print(f"Migrado Capturador: {cap.user.username}")

def revertir_migracion(apps, schema_editor):
    app_name = 'capturador_inventario_api'
    Empleado = apps.get_model(app_name, 'Empleado')
    Empleado.objects.all().delete()

class Migration(migrations.Migration):

    dependencies = [
        # IMPORTANTE: Reemplaza esto con el nombre real de tu última migración.
        # Generalmente es '0001_initial' si es la primera vez que tocas esto.
        ('capturador_inventario_api', '0010_alter_bitacorasincronizacion_id_empleado'), 
    ]

    operations = [
        migrations.RunPython(mover_datos_a_empleado, revertir_migracion),
    ]