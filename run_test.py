# run_test.py
import os
import django

# --- Configuración Inicial para Entorno Django ---
# Debes apuntar a la configuración de tu proyecto Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "capturador_inventario_api.settings") 
django.setup() 
# ---------------------------------------------------

# Importamos la clase MicrosipService desde la nueva ubicación
from capturador_inventario_api.microsip_api.microsip_api_sync_Articulos import InventariosService, prueba_1_sincronizacion
from capturador_inventario_api.models import Articulo, ClaveAuxiliar


if __name__ == '__main__':
    print("--- Inicializando ambiente de Django para prueba de Microsip API ---")
    
    # --------------------------------------------------------------------------
    # NOTA CRÍTICA PARA LA PRUEBA: 
    # Antes de ejecutar la prueba, asegúrate de que el modelo ClaveAuxiliar
    # (y Articulo) tenga aplicada la migración en tu base de datos local de Django.
    # --------------------------------------------------------------------------

    # La prueba 'prueba_1_conexion_lectura()' ahora orquesta la conexión, 
    # la sincronización y la validación de la caché local.
    if prueba_1_sincronizacion():
        print("\nPrueba de Conexión y Lectura FINALIZADA con éxito.")
    else:
        print("\nPrueba de Conexión y Lectura FALLIDA. Revisa los logs.")