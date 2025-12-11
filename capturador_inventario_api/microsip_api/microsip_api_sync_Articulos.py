from datetime import datetime, date
import traceback
import fdb  # REQUISITO: pip install fdb
from django.db import IntegrityError, transaction
from django.utils import timezone
from django.conf import settings # Para leer la config de conexión

# Importamos tus modelos
from capturador_inventario_api.models import (
    Articulo, 
    ClaveAuxiliar, 
    BitacoraSincronizacion, 
    Almacen, 
    InventarioArticulo
)
from .microsip_api_connection import MicrosipConnectionBase, microsip_connect, MicrosipAPIError 

# Mapa para la DLL (cuando escribamos en el futuro)
SEGUIMIENTO_MAP_OUT = {
    'N': 0,
    'L': 1,
    'S': 2,
}

class InventariosService(MicrosipConnectionBase): 
    """
    Servicio híbrido:
    - Usa SQL Directo (fdb) para LEER masivamente (Sync rápido).
    - Usa DLL Microsip para ESCRIBIR transacciones (Validación de negocio).
    """
    
    # -------------------------------------------------------------------------
    # GESTIÓN DE CONEXIÓN SQL DIRECTA (SOLO LECTURA)
    # -------------------------------------------------------------------------
    
    def _get_db_config(self):
        """Intenta obtener la configuración de BD desde settings.py"""
        if hasattr(settings, 'MICROSIP_CONFIG'):
            return settings.MICROSIP_CONFIG
        
        if hasattr(settings, 'DB_FILE'):
            return {
                'DB_FILE': settings.DB_FILE,
                'USER': getattr(settings, 'USER', 'SYSDBA'),
                'PASSWORD': getattr(settings, 'PASSWORD', 'masterkey'),
                'CHARSET': 'NONE' 
            }
        raise ValueError("No se encontró configuración de Microsip en settings.py")

    def _ejecutar_query_firebird(self, sql, params=None):
        conf = self._get_db_config()
        
        dsn = conf['DB_FILE']
        user = conf['USER']
        password = conf['PASSWORD']
        
        con = fdb.connect(
            dsn=dsn, 
            user=user, 
            password=password,
            charset='NONE' 
        )
        
        cursor = con.cursor()
        try:
            cursor.execute(sql, params or ())
            
            # Verificar si la consulta retorna resultados
            if cursor.description:
                columns = [col[0] for col in cursor.description]
                rows = cursor.fetchall()
                result = []
                for row in rows:
                    row_dict = {}
                    for i, col_name in enumerate(columns):
                        val = row[i]
                        if isinstance(val, str):
                            val = val.strip()
                        row_dict[col_name] = val
                    result.append(row_dict)
                return result
            else:
                return [] # Para sentencias que no retornan nada (aunque execute block returns sí retorna)
        finally:
            cursor.close()
            con.close()

    # -------------------------------------------------------------------------
    # 1. EXTRACCIÓN DE DATOS MAESTROS
    # -------------------------------------------------------------------------

    def extraer_articulos_y_claves_msip(self):
        print("-> 1. Extrayendo Artículos y Claves vía SQL Directo...")
        
        sql = """
            SELECT 
                A.ARTICULO_ID,
                A.NOMBRE,
                CA.CLAVE_ARTICULO,
                CA.ROL_CLAVE_ART_ID, 
                A.SEGUIMIENTO        
            FROM ARTICULOS A
            JOIN CLAVES_ARTICULOS CA ON CA.ARTICULO_ID = A.ARTICULO_ID
            WHERE A.ESTATUS = 'A'
        """
        
        rows = self._ejecutar_query_firebird(sql)
        
        temp_articulos = {}
        ids_activos = []

        for row in rows:
            art_id = row['ARTICULO_ID']
            nombre = row['NOMBRE']
            clave = row['CLAVE_ARTICULO']
            rol = row['ROL_CLAVE_ART_ID']
            
            seguimiento = row.get('SEGUIMIENTO', 'N')
            if not seguimiento: seguimiento = 'N'
            seguimiento = seguimiento.strip()

            if art_id not in temp_articulos:
                ids_activos.append(art_id)
                temp_articulos[art_id] = {
                    'nombre': nombre,
                    'seguimiento_tipo': seguimiento,
                    'claves': []
                }
            
            if clave:
                temp_articulos[art_id]['claves'].append((clave, rol))

        articulos_microsip = {} 
        claves_por_articulo = {} 

        for art_id, datos in temp_articulos.items():
            all_keys = datos['claves']
            clave_principal = None
            claves_auxiliares = []
            
            idx_principal = next((i for i, (k, r) in enumerate(all_keys) if r == 17), None)
            
            if idx_principal is not None:
                clave_principal = all_keys[idx_principal][0]
                for i, (k, r) in enumerate(all_keys):
                    if i != idx_principal:
                        claves_auxiliares.append(k)
            elif all_keys:
                clave_principal = all_keys[0][0]
                for i in range(1, len(all_keys)):
                    claves_auxiliares.append(all_keys[i][0])
            else:
                clave_principal = f"S/C-{art_id}"

            articulos_microsip[art_id] = {
                'nombre': datos['nombre'],
                'seguimiento_tipo': datos['seguimiento_tipo'],
                'clave': clave_principal
            }
            claves_por_articulo[art_id] = claves_auxiliares

        print(f"-> Extracción finalizada: {len(articulos_microsip)} artículos activos procesados.")
        return articulos_microsip, claves_por_articulo, ids_activos

    # -------------------------------------------------------------------------
    # 2. SINCRONIZACIÓN DE ALMACENES
    # -------------------------------------------------------------------------

    def _sincronizar_almacenes(self):
        print("-> 2. Sincronizando Almacenes...")
        sql = "SELECT ALMACEN_ID, NOMBRE FROM ALMACENES"
        almacenes_msip = self._ejecutar_query_firebird(sql)
        
        creados = 0
        actualizados = 0
        ids_activos = []

        for row in almacenes_msip:
            msip_id = row['ALMACEN_ID']
            nombre = row['NOMBRE']
            ids_activos.append(msip_id)

            obj, created = Almacen.objects.update_or_create(
                almacen_id_msip=msip_id,
                defaults={'nombre': nombre}
            )
            if created: creados += 1
            else: actualizados += 1
        
        Almacen.objects.exclude(almacen_id_msip__in=ids_activos).update(activo_web=False)
        return creados

    # -------------------------------------------------------------------------
    # 3. SINCRONIZACIÓN DE ARTÍCULOS
    # -------------------------------------------------------------------------

    def _actualizar_articulos_django(self, articulos_microsip, log_buffer):
        articulos_a_crear = []
        articulos_a_actualizar = []
        
        print("-> 3. Procesando artículos en Django...")
        
        articulos_existentes = {a.articulo_id_msip: a for a in Articulo.objects.all()}
        
        claves_registradas = {}
        for a in Articulo.objects.all():
            key_norm = a.clave.strip().upper()
            claves_registradas[key_norm] = a.articulo_id_msip

        for msip_id, data in articulos_microsip.items():
            clave_original = data['clave'].strip()
            clave_check = clave_original.upper()
            
            if clave_check in claves_registradas:
                dueno_id = claves_registradas[clave_check]
                
                if dueno_id != msip_id:
                    clave_candidata = f"{clave_original}_DUP_{msip_id}"
                    msg = f"⚠ AVISO: Clave duplicada '{clave_original}' (vs ID {dueno_id}). Se renombró a '{clave_candidata}' para el ID {msip_id}."
                    print(msg)
                    log_buffer.append(msg)
                    
                    clave_original = clave_candidata
                    clave_check = clave_candidata.upper()

            claves_registradas[clave_check] = msip_id
            
            articulo = articulos_existentes.get(msip_id)
            if articulo:
                clave_final = clave_original.upper()
                
                if (articulo.clave != clave_final or 
                    articulo.nombre != data['nombre'] or
                    articulo.seguimiento_tipo != data['seguimiento_tipo'] or
                    not articulo.activo):
                    
                    articulo.clave = clave_final
                    articulo.nombre = data['nombre']
                    articulo.seguimiento_tipo = data['seguimiento_tipo']
                    articulo.activo = True
                    articulos_a_actualizar.append(articulo)
            else:
                clave_final = clave_original.upper()
                articulos_a_crear.append(Articulo(
                    articulo_id_msip=msip_id,
                    clave=clave_final,
                    nombre=data['nombre'],
                    seguimiento_tipo=data['seguimiento_tipo'],
                    activo=True
                ))
        
        BATCH_SIZE = 1000
        if articulos_a_crear:
            Articulo.objects.bulk_create(articulos_a_crear, batch_size=BATCH_SIZE)
        
        if articulos_a_actualizar:
            Articulo.objects.bulk_update(articulos_a_actualizar, ['clave', 'nombre', 'seguimiento_tipo', 'activo'], batch_size=BATCH_SIZE)

        return len(articulos_a_crear), len(articulos_a_actualizar)

    def _limpiar_articulos_obsoletos(self, ids_microsip_activos):
        if not ids_microsip_activos: return 0
        return Articulo.objects.filter(activo=True).exclude(articulo_id_msip__in=ids_microsip_activos).update(activo=False)

    # -------------------------------------------------------------------------
    # 5. SINCRONIZACIÓN DE CLAVES AUXILIARES
    # -------------------------------------------------------------------------

    def _sincronizar_claves_auxiliares(self, ids_microsip_activos, claves_por_articulo):
        print("-> 5. Sincronizando claves auxiliares...")
        if ids_microsip_activos:
             pks_activos = Articulo.objects.filter(articulo_id_msip__in=ids_microsip_activos).values_list('pk', flat=True)
             ClaveAuxiliar.objects.filter(articulo_id__in=pks_activos).delete()

        articulos_map = {a.articulo_id_msip: a.pk for a in Articulo.objects.filter(articulo_id_msip__in=ids_microsip_activos)}
        
        claves_a_crear = []
        for msip_id, claves in claves_por_articulo.items():
            if msip_id in articulos_map:
                pk = articulos_map[msip_id]
                
                claves_procesadas_para_este_articulo = set()
                
                for clave in claves:
                    clave_clean = clave.strip().upper()
                    if clave_clean not in claves_procesadas_para_este_articulo:
                        claves_a_crear.append(ClaveAuxiliar(articulo_id=pk, clave=clave_clean))
                        claves_procesadas_para_este_articulo.add(clave_clean)

        if claves_a_crear:
            ClaveAuxiliar.objects.bulk_create(claves_a_crear, batch_size=2000)
            
        return len(claves_a_crear)

    # -------------------------------------------------------------------------
    # 6. SINCRONIZACIÓN DE INVENTARIO
    # -------------------------------------------------------------------------

    def _sincronizar_existencias_y_localizaciones(self):
        print("-> 6. Sincronizando Existencias usando procedimiento CALC_EXIS_ARTALM...")

        # USAMOS EXECUTE BLOCK PARA LLAMAR AL PROCEDIMIENTO ALMACENADO DE FORMA MASIVA
        # Esto soluciona que el procedimiento sea 'Executable' y no 'Selectable'.
        # Iteramos en el servidor Firebird, no en Python.
        
        sql_block = """
            EXECUTE BLOCK (P_FECHA DATE = ?) RETURNS (
                ARTICULO_ID INTEGER,
                ALMACEN_ID INTEGER,
                LOCALIZACION VARCHAR(50),
                STOCK_MIN NUMERIC(18,5),
                STOCK_MAX NUMERIC(18,5),
                PUNTO_REORDEN NUMERIC(18,5),
                EXISTENCIA NUMERIC(18,5)
            ) AS
            DECLARE VARIABLE V_COSTO NUMERIC(15,2);
            BEGIN
              FOR SELECT 
                    A.ARTICULO_ID, 
                    AL.ALMACEN_ID,
                    COALESCE(NA.LOCALIZACION, ''),
                    COALESCE(NA.INVENTARIO_MINIMO, 0),
                    COALESCE(NA.INVENTARIO_MAXIMO, 0),
                    COALESCE(NA.PUNTO_REORDEN, 0)
                  FROM ARTICULOS A
                  JOIN ALMACENES AL ON 1=1
                  LEFT JOIN NIVELES_ARTICULOS NA 
                    ON NA.ARTICULO_ID = A.ARTICULO_ID AND NA.ALMACEN_ID = AL.ALMACEN_ID
                  WHERE A.ESTATUS = 'A'
                  INTO :ARTICULO_ID, :ALMACEN_ID, :LOCALIZACION, :STOCK_MIN, :STOCK_MAX, :PUNTO_REORDEN
              DO
              BEGIN
                  /* LLAMADA AL PROCEDIMIENTO PROPORCIONADO POR EL USUARIO */
                  EXECUTE PROCEDURE CALC_EXIS_ARTALM(:ARTICULO_ID, :ALMACEN_ID, :P_FECHA)
                  RETURNING_VALUES :EXISTENCIA, :V_COSTO;
                  
                  SUSPEND;
              END
            END
        """
        
        # Pasamos la fecha actual
        fecha_corte = date.today()
        
        datos_msip = self._ejecutar_query_firebird(sql_block, (fecha_corte,))
        
        map_articulos = {a.articulo_id_msip: a.pk for a in Articulo.objects.all()}
        map_almacenes = {al.almacen_id_msip: al.pk for al in Almacen.objects.all()}
        
        inventario_actual = {
            (inv.articulo_id, inv.almacen_id): inv 
            for inv in InventarioArticulo.objects.all()
        }

        updates = []
        creates = []

        for row in datos_msip:
            msip_art_id = row['ARTICULO_ID']
            msip_alm_id = row['ALMACEN_ID']

            django_art_id = map_articulos.get(msip_art_id)
            django_alm_id = map_almacenes.get(msip_alm_id)

            if not django_art_id or not django_alm_id: continue

            inv_obj = inventario_actual.get((django_art_id, django_alm_id))
            
            nueva_exist = row['EXISTENCIA']
            nueva_loc = row['LOCALIZACION']
            
            if inv_obj:
                loc_a_guardar = inv_obj.localizacion
                if not inv_obj.pendiente_sincronizar_msip:
                    loc_a_guardar = nueva_loc
                
                if (inv_obj.existencia != nueva_exist or 
                    inv_obj.localizacion != loc_a_guardar or
                    inv_obj.stock_minimo != row['STOCK_MIN']):
                    
                    inv_obj.existencia = nueva_exist
                    inv_obj.localizacion = loc_a_guardar
                    inv_obj.stock_minimo = row['STOCK_MIN']
                    inv_obj.stock_maximo = row['STOCK_MAX']
                    inv_obj.punto_reorden = row['PUNTO_REORDEN']
                    updates.append(inv_obj)
            else:
                creates.append(InventarioArticulo(
                    articulo_id=django_art_id,
                    almacen_id=django_alm_id,
                    existencia=nueva_exist,
                    localizacion=nueva_loc,
                    stock_minimo=row['STOCK_MIN'],
                    stock_maximo=row['STOCK_MAX'],
                    punto_reorden=row['PUNTO_REORDEN']
                ))

        if creates: InventarioArticulo.objects.bulk_create(creates, batch_size=2000)
        if updates: InventarioArticulo.objects.bulk_update(updates, ['existencia', 'localizacion', 'stock_minimo', 'stock_maximo', 'punto_reorden'], batch_size=2000)
        
        return len(creates) + len(updates)

    # -------------------------------------------------------------------------
    # ORQUESTADOR PRINCIPAL
    # -------------------------------------------------------------------------

    @microsip_connect
    def sincronizar_articulos(self):
        print("--- INICIANDO ORQUESTADOR DE SINCRONIZACIÓN (MODO HÍBRIDO) ---")
        bitacora = BitacoraSincronizacion.objects.create(status='EN_PROCESO')
        log_buffer = []

        try:
            articulos_msip, claves_msip, ids_activos = self.extraer_articulos_y_claves_msip()
            bitacora.articulos_procesados = len(articulos_msip)

            with transaction.atomic():
                self._sincronizar_almacenes()
                creados, actualizados = self._actualizar_articulos_django(articulos_msip, log_buffer)
                desactivados = self._limpiar_articulos_obsoletos(ids_activos)
                claves_creadas = self._sincronizar_claves_auxiliares(ids_activos, claves_msip)
                inventarios_proc = self._sincronizar_existencias_y_localizaciones()

            bitacora.articulos_creados = creados
            bitacora.articulos_actualizados = actualizados
            bitacora.articulos_desactivados = desactivados
            bitacora.detalles = f"Sync OK. Inv: {inventarios_proc}. Claves: {claves_creadas}"
            bitacora.status = 'EXITO'
            bitacora.fecha_fin = timezone.now()
            bitacora.save()

            print("--- SINCRONIZACIÓN EXITOSA ---")
            return {
                "articulos_creados": creados,
                "articulos_actualizados": actualizados,
                "inventarios_procesados": inventarios_proc
            }

        except Exception as e:
            error_msg = traceback.format_exc()
            print(f"!!! ERROR FATAL !!!: {e}")
            bitacora.status = 'ERROR'
            bitacora.mensaje_error = error_msg
            bitacora.fecha_fin = timezone.now()
            bitacora.save()
            raise e