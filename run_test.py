import os
import django
import sys
import time

# --- 1. Configuración del Entorno Django ---
print("⚙️  Cargando configuración de Django...")
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "capturador_inventario_api.settings") 
django.setup() 
print("✅ Django cargado correctamente.\n")

# --- 2. Importaciones (Después del setup) ---
from django.db.models import Sum
from capturador_inventario_api.microsip_api.microsip_api_sync_Articulos import InventariosService
from capturador_inventario_api.microsip_api.microsip_api_connection import MicrosipAPIError
from capturador_inventario_api.models import Articulo, ClaveAuxiliar, Almacen, InventarioArticulo

def imprimir_separador(titulo):
    print(f"\n{'='*60}")
    print(f" {titulo}")
    print(f"{'='*60}")

def ejecutar_prueba_completa():
    imprimir_separador("🚀 INICIANDO PRUEBA DE SINCRONIZACIÓN HÍBRIDA")
    
    # Instanciamos el servicio
    service = InventariosService()
    
    start_time = time.time()
    
    try:
        # ---------------------------------------------------------
        # PASO 1: EJECUCIÓN DEL PROCESO
        # ---------------------------------------------------------
        print("⏳ Conectando a Firebird y extrayendo datos...")
        
        # Llamamos al método principal que orquesta todo
        resultados = service.sincronizar_articulos()
        
        end_time = time.time()
        duracion = end_time - start_time
        
        # ---------------------------------------------------------
        # PASO 2: REPORTE DE EJECUCIÓN (LO QUE HIZO EL SCRIPT)
        # ---------------------------------------------------------
        imprimir_separador("📊 RESULTADOS DE LA SINCRONIZACIÓN")
        print(f"⏱️  Tiempo de ejecución: {duracion:.2f} segundos")
        print(f"--------------------------------------------------")
        print(f"📦 Artículos Creados      : {resultados.get('articulos_creados', 0)}")
        print(f"📝 Artículos Actualizados : {resultados.get('articulos_actualizados', 0)}")
        print(f"🏭 Inventarios Procesados : {resultados.get('inventarios_procesados', 0)}")
        print(f"--------------------------------------------------")

        # ---------------------------------------------------------
        # PASO 3: AUDITORÍA DE BASE DE DATOS (LO QUE REALMENTE HAY)
        # ---------------------------------------------------------
        imprimir_separador("🗄️  ESTADO ACTUAL DE LA BASE DE DATOS (DJANGO)")
        
        total_articulos = Articulo.objects.count()
        articulos_activos = Articulo.objects.filter(activo=True).count()
        total_claves = ClaveAuxiliar.objects.count()
        total_almacenes = Almacen.objects.count()
        total_inventario = InventarioArticulo.objects.count()
        
        print(f"📌 Total Artículos       : {total_articulos} ({articulos_activos} Activos)")
        print(f"📌 Total Claves Aux.     : {total_claves}")
        print(f"📌 Total Almacenes       : {total_almacenes}")
        print(f"📌 Registros Inventario  : {total_inventario}")

        # ---------------------------------------------------------
        # PASO 4: MUESTRA DE DATOS (VERIFICACIÓN VISUAL)
        # ---------------------------------------------------------
        if total_inventario > 0:
            imprimir_separador("🔎 MUESTRA ALEATORIA DE INVENTARIO")
            # Tomamos un registro de inventario que tenga existencia > 0 para que sea interesante
            muestra = InventarioArticulo.objects.filter(existencia__gt=0).select_related('articulo', 'almacen').first()
            
            if muestra:
                print(f"Articulo:      {muestra.articulo.clave} - {muestra.articulo.nombre}")
                print(f"Almacén:       {muestra.almacen.nombre}")
                print(f"Ubicación:     [{muestra.localizacion}]")
                print(f"Existencia:    {muestra.existencia:.2f}")
                print(f"Stock Mínimo:  {muestra.stock_minimo:.2f}")
                print("\n✅ CONCLUSIÓN: La consulta SQL híbrida funcionó correctamente.")
            else:
                print("⚠️  Hay registros de inventario, pero todos tienen existencia 0.")
        else:
            print("\n⚠️  ALERTA: No se crearon registros de inventario. Revisa si hay almacenes activos en Microsip.")

    except MicrosipAPIError as e:
        print(f"\n❌ ERROR DE API MICROSIP: {e}")
        print(f"Detalles: {e.details}")
    
    except Exception as e:
        print(f"\n❌ ERROR CRÍTICO DEL SISTEMA:")
        print(str(e))
        import traceback
        traceback.print_exc()

if __name__ == '__main__':
    ejecutar_prueba_completa()