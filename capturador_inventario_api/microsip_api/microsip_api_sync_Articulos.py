from datetime import datetime
from django.db import IntegrityError, transaction 

# Importaciones de Django Models
from capturador_inventario_api.models import Articulo, ClaveAuxiliar 

# Importación de la capa de conexión y base de datos, 
# incluyendo el decorador si se hubiera definido en un archivo separado.
# NOTA: Ahora el decorador y la excepción están en microsip_api_connection.py
from .microsip_api_connection import MicrosipConnectionBase, SEGUIMIENTO_MAP_IN, microsip_connect, MicrosipAPIError 

# Mapa inverso: de Char (Django) a Integer esperado por la DLL (Microsip)
SEGUIMIENTO_MAP_OUT = {
    'N': 0,
    'L': 1,
    'S': 2,
}


class InventariosService(MicrosipConnectionBase): # Cambié el nombre a InventariosService para ser más específico
    """
    Clase de servicio que contiene la lógica de negocio de Django (ORM)
    y orquesta las llamadas de bajo nivel a la DLL para el módulo de Inventarios.
    Hereda la conexión, desconexión y la extracción/registro de la base.
    """
    
    # ... (Métodos de soporte: _actualizar_articulos_django, _limpiar_articulos_obsoletos, _sincronizar_claves_auxiliares se mantienen igual)
    
    def _actualizar_articulos_django(self, articulos_microsip):
        # [CONTENIDO OMITIDO - Lógica de Django ORM]
        pass
        
    def _limpiar_articulos_obsoletos(self, ids_microsip_activos):
        # [CONTENIDO OMITIDO - Lógica de Django ORM]
        pass
        
    def _sincronizar_claves_auxiliares(self, ids_microsip_activos, claves_por_articulo):
        # [CONTENIDO OMITIDO - Lógica de Django ORM]
        pass

    @microsip_connect
    def sincronizar_articulos(self):
        """
        Punto de entrada principal para el job de sincronización.
        Orquestador: Controla el flujo completo de sincronización de la caché.
        
        NOTA: La conexión/desconexión es manejada por @microsip_connect.
        """
        print("--- INICIANDO ORQUESTADOR DE SINCRONIZACIÓN DE CATÁLOGO (Inventarios) ---")
        
        # 1. Extracción de datos de Microsip (Llamada a la función DECORADA de la base)
        # Si falla, el decorador lo captura y desconecta.
        articulos_microsip, claves_por_articulo, ids_microsip_activos = self.extraer_articulos_y_claves_msip()
        
        # 2. Transacción de Django: Asegura la atomicidad de la caché local
        with transaction.atomic():
            # 2.1. Carga de Artículos Principales (Crear/Actualizar)
            creados, actualizados = self._actualizar_articulos_django(articulos_microsip)
            
            # 2.2. Limpieza de Artículos Obsoletos (Barrido)
            eliminados_articulos = self._limpiar_articulos_obsoletos(ids_microsip_activos)
            
            # 2.3. Sincronización de Claves Auxiliares (Limpiar y Recrear)
            claves_creadas = self._sincronizar_claves_auxiliares(ids_microsip_activos, claves_por_articulo)

        print("--- ORQUESTACIÓN FINALIZADA CON ÉXITO ---")
        return {
            "articulos_creados": creados,
            "articulos_actualizados": actualizados,
            "articulos_eliminados": eliminados_articulos,
            "claves_creadas": claves_creadas,
        }

    @microsip_connect
    def registrar_entrada(self, encabezado_data, renglones_data):
        """
        Implementa la lógica de negocio para validar la caché y registrar la Entrada en Microsip.
        
        NOTA: La conexión/desconexión y Aborto si falla la DLL son manejados por @microsip_connect.
        """
        
        # 1. Validar la caché (traducir claves auxiliares a IDs de Microsip y tipos de seguimiento)
        renglones_msip = []
        for renglon in renglones_data:
            clave_busqueda = renglon['ArticuloId'] # ArticuloId aquí es la CLAVE/CÓDIGO AUXILIAR
            
            try:
                # Búsqueda en el modelo ClaveAuxiliar, que usa el índice por 'clave'
                clave_aux = ClaveAuxiliar.objects.select_related('articulo').get(clave=clave_busqueda)
                articulo_cache = clave_aux.articulo
                
                articulo_id_final = articulo_cache.articulo_id_msip
                articulo_nombre = articulo_cache.nombre
                # Mapear el char de Django ('L', 'S', 'N') al Integer de la DLL (1, 2, 0)
                seguimiento = SEGUIMIENTO_MAP_OUT.get(articulo_cache.seguimiento_tipo, 0) 
                
                # Crear el renglón para pasar a la DLL
                renglones_msip.append({
                    'ArticuloId': articulo_id_final, 
                    'Unidades': renglon['Unidades'],
                    'CostoUnitario': renglon.get('CostoUnitario', 0.0),
                    'CostoTotal': renglon.get('CostoTotal', 0.0),
                    'Seguimiento': seguimiento, 
                    'Nombre': articulo_nombre, 
                    'Lotes': renglon.get('Lotes', []), 
                    'Series': renglon.get('Series', []), 
                })
                
            except ClaveAuxiliar.DoesNotExist:
                # Lanzar un error claro para el frontend/consumidor
                raise ValueError(f"Artículo con clave {clave_busqueda} no encontrado en caché local. Sincronice el catálogo.")

        # 2. Llamar a la función DECORADA de la base para registrar el documento en Microsip
        # Si falla AplicaEntrada o cualquier Renglon, se lanza MicrosipAPIError y el decorador ABORTA la transacción.
        return self.registrar_entrada_msip(encabezado_data, renglones_msip)



# --- ----------------------------------------------------------- ---
# --- PRUEBA DE CONEXIÓN Y LECTURA (Bajo Impacto) ---
# --- ----------------------------------------------------------- ---

def prueba_1_conexion_lectura():
    """
    Función de prueba para el flujo de sincronización.
    """
    print("=============================================")
    print("🚀 INICIANDO PRUEBA 1: CONEXIÓN Y SINCRONIZACIÓN")
    print("=============================================")
    
    # NOTA: La clase ahora se inicializa sin parámetros, leyendo de settings.py
    service = InventariosService()
    
    try:
        service.conectar()
        print("\n✅ Conexión con la API de Microsip establecida.")

        # --- Prueba de Sincronización (NUEVA PRUEBA) ---
        print("\n--- INICIANDO PRUEBA DE SINCRONIZACIÓN DE CATÁLOGO ---")
        
        # Usamos sincronizar_articulos_completo() directamente
        resultados = service.sincronizar_articulos()
        
        print("--- PRUEBA DE SINCRONIZACIÓN FINALIZADA ---")
        print(f"Resumen: Creados={resultados['articulos_creados']}, Actualizados={resultados['articulos_actualizados']}, Eliminados={resultados['articulos_eliminados']}, Claves Creadas={resultados['claves_creadas']}")


        # --- Paso 2: Consulta Segura (Simulación de búsqueda de artículo conocido) ---

        # Simulación de búsqueda en caché (requiere que la prueba anterior haya corrido)
        # NOTA: Esta clave debe ser una que realmente se encuentre en CLAVES_ARTICULOS en la BD de Microsip
        CLAVE_AUXILIAR_DE_PRUEBA = '7501247418502' 
        
        try:
            # Ahora la búsqueda usa el nuevo modelo ClaveAuxiliar
            clave_obj = ClaveAuxiliar.objects.select_related('articulo').get(clave=CLAVE_AUXILIAR_DE_PRUEBA)
            articulo_en_cache = clave_obj.articulo

            # Verificación del campo clave en el objeto Articulo (ya no es codigo_barras)
            articulo_clave_principal = articulo_en_cache.clave 
            
            print(f"\n✅ Búsqueda en caché exitosa (Django ORM):")
            print(f"    > Clave de búsqueda: {CLAVE_AUXILIAR_DE_PRUEBA}")
            print(f"    > Clave Principal (Microsip): {articulo_clave_principal}")
            print(f"    > Nombre: {articulo_en_cache.nombre}")
            print(f"    > ID Microsip: {articulo_en_cache.articulo_id_msip}")
            print(f"    > Tipo de Seguimiento: {articulo_en_cache.seguimiento_tipo}")
            
        except ClaveAuxiliar.DoesNotExist:
            print(f"\n❌ FALLO de Búsqueda: La clave auxiliar '{CLAVE_AUXILIAR_DE_PRUEBA}' no fue sincronizada o no existe en la caché local.")
            
    except Exception as e:
        print(f"\n❌ FALLO DE PRUEBA: Error durante el ciclo de vida o consulta.")
        print(f"    Causa del error: {e}")
        return False
        
    finally:
        # Paso 3: Desconexión y Liberación de Licencia (CRÍTICO)
        service.desconectar()
        print("\n✅ Desconexión de la API y liberación de licencia completada.")
        print("=============================================")
        return True