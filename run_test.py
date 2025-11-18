# run_test.py
import os
import django

# --- Configuración Inicial para Entorno Django ---
# Debes apuntar a la configuración de tu proyecto Django
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "capturador_inventario_api.settings") 
django.setup() 
# ---------------------------------------------------

from capturador_inventario_api.microsip_api.microsip_service import prueba_1_conexion_lectura
# Nota: Ajusta la importación de 'tu_app' al nombre real de tu aplicación

if __name__ == '__main__':
    print("--- Inicializando ambiente de Django para prueba de Microsip API ---")
    
    # Llama a la función de prueba
    if prueba_1_conexion_lectura():
        print("\nPrueba de Conexión y Lectura FINALIZADA con éxito.")
    else:
        print("\nPrueba de Conexión y Lectura FALLIDA. Revisa los logs.")