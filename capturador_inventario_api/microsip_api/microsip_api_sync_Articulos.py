from datetime import datetime
import traceback
from django.db import IntegrityError, transaction
from django.utils import timezone

from capturador_inventario_api.models import Articulo, ClaveAuxiliar, BitacoraSincronizacion
# Corregido: Quitamos SEGUIMIENTO_MAP_OUT del import porque lo definiremos abajo
from .microsip_api_connection import MicrosipConnectionBase, SEGUIMIENTO_MAP_IN, microsip_connect, MicrosipAPIError 

# Mapa inverso: de Char (Django) a Integer esperado por la DLL (Microsip)
# RESTAURADO: Definición local para evitar errores de importación
SEGUIMIENTO_MAP_OUT = {
    'N': 0,
    'L': 1,
    'S': 2,
}


class InventariosService(MicrosipConnectionBase): 
    """
    Clase de servicio que contiene la lógica de negocio de Django (ORM)
    y orquesta las llamadas de bajo nivel a la DLL para el módulo de Inventarios.
    """
    
    def _actualizar_articulos_django(self, articulos_microsip, log_buffer):
        """
        Carga de Artículos Principales: Inserta/Actualiza la tabla Articulo en Django.
        Retorna la tupla (creados, actualizados).
        AÑADIDO: Recibe log_buffer para acumular errores en lugar de solo imprimir.
        """
        articulos_a_crear = []
        articulos_a_actualizar = []
        
        print("-> 3. Procesando artículos principales en Django...")
        print("   Iniciando preparación de objetos para la base de datos local...") 
        
        for msip_id, data in articulos_microsip.items():
            try:
                # Intentamos obtener el artículo existente
                articulo = Articulo.objects.get(articulo_id_msip=msip_id)
                
                # Verificamos cambios
                if (articulo.clave != data['clave'] or 
                    articulo.nombre != data['nombre'] or
                    articulo.seguimiento_tipo != data['seguimiento_tipo'] or
                    not articulo.activo):

                    articulo.clave = data['clave']
                    articulo.nombre = data['nombre']
                    articulo.seguimiento_tipo = data['seguimiento_tipo']
                    articulo.activo = True 
                    articulos_a_actualizar.append(articulo)
                
            except Articulo.DoesNotExist:
                # Si no existe, agregar a lista de creación
                articulos_a_crear.append(Articulo(
                    articulo_id_msip=msip_id,
                    clave=data['clave'],
                    nombre=data['nombre'],
                    seguimiento_tipo=data['seguimiento_tipo'],
                    activo=True 
                ))
            except IntegrityError as e:
                # CAPTURA DE ERROR: Lo imprimimos Y lo guardamos en la bitácora
                msg = f"Advertencia (Integridad): Error al procesar artículo ID {msip_id}: {e}"
                print(msg)
                log_buffer.append(msg)
        
        BATCH_SIZE = 1000

        if articulos_a_crear:
            print(f"   Insertando {len(articulos_a_crear)} nuevos artículos en lotes de {BATCH_SIZE}...")
            Articulo.objects.bulk_create(articulos_a_crear, batch_size=BATCH_SIZE, ignore_conflicts=True)
        
        if articulos_a_actualizar:
            print(f"   Actualizando {len(articulos_a_actualizar)} artículos existentes en lotes de {BATCH_SIZE}...")
            Articulo.objects.bulk_update(articulos_a_actualizar, ['clave', 'nombre', 'seguimiento_tipo', 'activo'], batch_size=BATCH_SIZE)

        print(f"-> Artículos Django: Creados {len(articulos_a_crear)}, Actualizados {len(articulos_a_actualizar)}.")
        
        return len(articulos_a_crear), len(articulos_a_actualizar)


    def _limpiar_articulos_obsoletos(self, ids_microsip_activos):
        """
        Limpieza Obsoleta: Desactiva (Soft Delete) artículos de Django que ya no están activos en Microsip.
        """
        print("-> 4. Limpiando artículos obsoletos (Soft Delete)...")
        
        if not ids_microsip_activos:
            return 0
            
        total_desactivados = Articulo.objects.filter(activo=True).exclude(articulo_id_msip__in=ids_microsip_activos).update(activo=False)
        
        print(f"-> Artículos obsoletos desactivados: {total_desactivados}")
        return total_desactivados


    def _sincronizar_claves_auxiliares(self, ids_microsip_activos, claves_por_articulo):
        """
        Sincronización de Claves: Borra y recrea las claves auxiliares.
        """
        print("-> 5. Sincronizando claves auxiliares...")

        # 1. Limpiar
        if ids_microsip_activos:
            claves_a_limpiar = ClaveAuxiliar.objects.filter(articulo__articulo_id_msip__in=ids_microsip_activos)
            total_limpiadas, _ = claves_a_limpiar.delete()
            print(f"-> Claves auxiliares limpiadas: {total_limpiadas}")


        # 2. Mapeo rápido de ID Microsip -> ID Django (PK)
        articulos_map = {
            a.articulo_id_msip: a.pk 
            for a in Articulo.objects.filter(articulo_id_msip__in=ids_microsip_activos)
        }
        
        # 3. Preparar objetos
        claves_a_crear = []
        for msip_id, claves in claves_por_articulo.items():
            if msip_id in articulos_map:
                articulo_pk = articulos_map[msip_id]
                for clave in claves:
                    claves_a_crear.append(ClaveAuxiliar(
                        articulo_id=articulo_pk,
                        clave=clave
                    ))

        BATCH_SIZE = 2000

        # 4. Ejecutar creación
        if claves_a_crear:
            print(f"   Insertando {len(claves_a_crear)} claves auxiliares en lotes de {BATCH_SIZE}...")
            ClaveAuxiliar.objects.bulk_create(claves_a_crear, batch_size=BATCH_SIZE, ignore_conflicts=True)
        
        print(f"-> Claves auxiliares creadas: {len(claves_a_crear)}")
        return len(claves_a_crear)


    @microsip_connect
    def sincronizar_articulos(self):
        """
        Punto de entrada principal para el job de sincronización.
        AHORA CON OBSERVABILIDAD DETALLADA.
        """
        print("--- INICIANDO ORQUESTADOR DE SINCRONIZACIÓN DE CATÁLOGO (Inventarios) ---")
        
        # 1. INICIO DE BITÁCORA
        bitacora = BitacoraSincronizacion.objects.create(status='EN_PROCESO')
        
        # Buffer para guardar logs específicos (ej. artículos problemáticos)
        log_buffer = []

        try:
            # 2. Extracción
            articulos_microsip, claves_por_articulo, ids_microsip_activos = self.extraer_articulos_y_claves_msip()
            
            bitacora.articulos_procesados = len(articulos_microsip)
            
            # 3. Transacción de Django
            with transaction.atomic():
                # Pasamos log_buffer para capturar errores individuales sin detener el proceso masivo
                creados, actualizados = self._actualizar_articulos_django(articulos_microsip, log_buffer)
                
                desactivados_articulos = self._limpiar_articulos_obsoletos(ids_microsip_activos)
                
                claves_creadas = self._sincronizar_claves_auxiliares(ids_microsip_activos, claves_por_articulo)

            # 4. ÉXITO DE BITÁCORA: Guardamos contadores extendidos y logs
            bitacora.articulos_creados = creados
            bitacora.articulos_actualizados = actualizados
            bitacora.articulos_desactivados = desactivados_articulos # NUEVO
            bitacora.claves_creadas = claves_creadas # NUEVO
            
            # Guardamos los mensajes acumulados (si los hay)
            if log_buffer:
                bitacora.detalles_procesamiento = "\n".join(log_buffer)
            
            bitacora.status = 'EXITO'
            bitacora.fecha_fin = timezone.now()
            bitacora.save()

            print("--- ORQUESTACIÓN FINALIZADA CON ÉXITO ---")
            return {
                "articulos_creados": creados,
                "articulos_actualizados": actualizados,
                "articulos_desactivados": desactivados_articulos, 
                "claves_creadas": claves_creadas,
            }

        except Exception as e:
            # 5. ERROR FATAL: Guardamos el traceback y lo que hayamos acumulado en log_buffer
            error_msg = traceback.format_exc()
            print(f"!!! ERROR FATAL EN SINCRONIZACIÓN !!!: {e}")
            
            bitacora.status = 'ERROR'
            bitacora.mensaje_error = error_msg
            
            # Si hubo logs parciales antes del crash, los guardamos también
            if log_buffer:
                bitacora.detalles_procesamiento = "\n".join(log_buffer)
                
            bitacora.fecha_fin = timezone.now()
            bitacora.save()
            
            raise e


    @microsip_connect
    def registrar_entrada(self, encabezado_data, renglones_data):
        """
        Implementa la lógica de negocio para validar la caché y registrar la Entrada en Microsip.
        """
        
        # 1. Validar la caché (traducir claves auxiliares a IDs de Microsip y tipos de seguimiento)
        renglones_msip = []
        for renglon in renglones_data:
            clave_busqueda = renglon['ArticuloId']
            
            try:
                # Búsqueda en el modelo ClaveAuxiliar, que usa el índice por 'clave'
                clave_aux = ClaveAuxiliar.objects.select_related('articulo').get(clave=clave_busqueda)
                articulo_cache = clave_aux.articulo

                # VALIDACIÓN ADICIONAL: ¿Permitimos usar artículos inactivos?
                if not articulo_cache.activo:
                     raise ValueError(f"El artículo '{articulo_cache.nombre}' está marcado como INACTIVO/OBSOLETO.")
                
                articulo_id_final = articulo_cache.articulo_id_msip
                articulo_nombre = articulo_cache.nombre
                # Mapear el char de Django ('L', 'S', 'N') al Integer de la DLL (1, 2, 0)
                seguimiento = SEGUIMIENTO_MAP_OUT.get(articulo_cache.seguimiento_tipo, 0) 
                
                # Crear el renglón para pasar a la DLL, incluyendo los datos de seguimiento
                renglones_msip.append({
                    'ArticuloId': articulo_id_final, 
                    'Unidades': renglon['Unidades'],
                    'CostoUnitario': renglon.get('CostoUnitario', 0.0),
                    'CostoTotal': renglon.get('CostoTotal', 0.0),
                    'Seguimiento': seguimiento, # Agregamos el tipo de seguimiento
                    'Nombre': articulo_nombre, # Agregamos el nombre para logs
                    'Lotes': renglon.get('Lotes', []), 
                    'Series': renglon.get('Series', []), 
                })
                
            except ClaveAuxiliar.DoesNotExist:
                raise ValueError(f"Artículo con clave {clave_busqueda} no encontrado en caché local. Sincronice el catálogo.")

        # 2. Llamar a la función de la base para registrar el documento en Microsip
        return self.registrar_entrada_msip(encabezado_data, renglones_msip)

# --- ----------------------------------------------------------- ---
# --- FUNCIÓN DE PRUEBA DE SINCRONIZACIÓN (Para run_test.py) ---
# --- ----------------------------------------------------------- ---

def prueba_1_sincronizacion():
    """
    Función de prueba para el flujo de sincronización del catálogo.
    Esta función NO debe ser decorada, ya que la conexión es manejada por el método interno.
    """
    print("=============================================")
    print("🚀 INICIANDO PRUEBA 1: CONEXIÓN Y SINCRONIZACIÓN")
    print("=============================================")
    
    # Inicializamos el servicio (lee la config de settings.py)
    service = InventariosService()
    
    try:
        # Aquí NO llamamos a .conectar(), se hace automáticamente por el decorador @microsip_connect
        # en el método .sincronizar_articulos()
        
        # --- Prueba de Sincronización ---
        print("\n--- INICIANDO PRUEBA DE SINCRONIZACIÓN DE CATÁLOGO ---")
        
        # La llamada a sincronizar_articulos inicia la conexión, ejecuta todo y la cierra al finalizar.
        resultados = service.sincronizar_articulos()
        
        print("--- PRUEBA DE SINCRONIZACIÓN FINALIZADA ---")
        print(f"Resumen: Creados={resultados['articulos_creados']}, Actualizados={resultados['articulos_actualizados']}, Desactivados={resultados['articulos_desactivados']}, Claves Creadas={resultados['claves_creadas']}")

        # Prueba de consulta de seguridad post-sincronización
        try:
            # Usamos una clave que sepamos que existe o tomamos la primera que encontremos
            articulo_test = Articulo.objects.filter(activo=True).first()
            if articulo_test:
                print(f"\n✅ Verificación de caché: Se encontró artículo ACTIVO '{articulo_test.nombre}' (ID: {articulo_test.articulo_id_msip})")
            else:
                print("\n⚠️ Advertencia: La sincronización terminó pero no hay artículos activos.")
        except Exception as db_e:
            print(f"\n❌ Error al consultar la base de datos local: {db_e}")
            
    except MicrosipAPIError as e:
        print(f"\n❌ FALLO DE PRUEBA: Error específico de la API de Microsip.")
        print(f"    Causa del error: {e}")
        print(f"    Detalles: {e.details}")
        return False
        
    except Exception as e:
        print(f"\n❌ FALLO DE PRUEBA: Error durante el ciclo de vida o consulta.")
        print(f"    Causa del error: {e}")
        import traceback
        traceback.print_exc()
        return False
        
    finally:
        # No se necesita desconectar aquí, el decorador se encargó de ello.
        print("=============================================")
        return True