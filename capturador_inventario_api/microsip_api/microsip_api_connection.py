from ctypes import c_int, c_char_p, c_double, byref, create_string_buffer, windll, POINTER, c_char
from django.conf import settings 
from django.core.exceptions import ImproperlyConfigured
from capturador_inventario_api.microsip_api.microsip_api import microsip_dll
from functools import wraps
from datetime import datetime # Se usa para el log de errores

# --- EXCEPCIONES PERSONALIZADAS ---
class MicrosipAPIError(Exception):
    """Excepción base para errores específicos de la API de Microsip."""
    def __init__(self, message, api_error_code=None, api_function=None, basic_error_code=None):
        super().__init__(message)
        self.api_error_code = api_error_code
        self.api_function = api_function
        self.basic_error_code = basic_error_code
        self.details = f"Código API: {api_error_code}. Función: {api_function or 'N/A'}. Código Básico: {basic_error_code or 'N/A'}."

# --- DECORADOR DE CONEXIÓN ---

def microsip_connect(func):
    """
    Decorador que gestiona automáticamente el ciclo de vida de la conexión y 
    desconexión de la API de Microsip para cualquier método de la clase de servicio.
    """
    @wraps(func)
    def wrapper(self, *args, **kwargs):
        # 1. Conectar (Si no está conectado)
        if not self.microsip_connected:
            self.conectar()
            
        try:
            # 2. Ejecutar la función decorada
            result = func(self, *args, **kwargs)
            return result
        
        except MicrosipAPIError as e:
            # Si hay un error al registrar un documento, siempre se aborta la transacción
            try:
                if self.is_connected:
                    microsip_dll.AbortaDoctoInventarios()
                    print(f"DEBUG: Transacción de Microsip abortada después del error: {e}")
            except Exception as abort_e:
                print(f"ADVERTENCIA: Fallo al intentar abortar la transacción: {abort_e}")
            
            raise e
            
        finally:
            # 3. Desconectar
            if self.microsip_connected:
                self.desconectar()

    return wrapper


# NOTA: Debemos declarar la función GetLastErrorCode de la API Básica aquí
try:
    microsip_dll.GetLastErrorCode.restype = c_int
except AttributeError:
    pass

# Mapeo de valores de SEGUIMIENTO (Microsip Integer) a Django Char
SEGUIMIENTO_MAP_IN = {
    0: 'N',  # Ninguno
    1: 'L',  # Lotes
    2: 'S',  # Series
}

class MicrosipConnectionBase:
    """
    Clase base que gestiona la conexión de bajo nivel, los handles y la comunicación
    con la ApiMicrosip.dll.
    """
    def __init__(self):
        try:
            config = settings.MICROSIP_CONFIG
        except AttributeError:
             raise ImproperlyConfigured("La configuración MICROSIP_CONFIG no está definida en settings.py.")

        # Handles internos de conexión
        self.db_handle = microsip_dll.NewDB()
        
        # Transacción Snapshot (Read-Only) para evitar bloqueos en lecturas masivas
        self.trn_handle = microsip_dll.NewTrn(self.db_handle, 0) 
        
        self.db_file = config['DB_FILE'].encode('latin-1')
        self.user = config['USER'].encode('latin-1')
        self.password = config['PASSWORD'].encode('latin-1')
        
        self.is_connected = False
        self.microsip_connected = False

    def _get_api_error_message(self, bookmark="", function_name=""):
        """Recupera el mensaje de error de la API y lanza una excepción limpia."""
        error_buffer = create_string_buffer(256)
        error_code = microsip_dll.inGetLastErrorMessage(error_buffer)
        basic_error_code = microsip_dll.GetLastErrorCode()
        error_message = error_buffer.value.decode('latin-1', errors='ignore').strip()

        if error_code != 0:
            full_message = f"Error en {function_name} ({bookmark}). Código: {error_code}. Mensaje: {error_message}"
            raise MicrosipAPIError(
                full_message, 
                api_error_code=error_code,
                api_function=function_name,
                basic_error_code=basic_error_code
            )
        return None

    def conectar(self):
        """Establece la conexión a la BD Microsip e inicia la transacción."""
        try:
            microsip_dll.inSetErrorHandling(0, 0)
            
            # 1. Conexión a la BD
            result = microsip_dll.DBConnect(self.db_handle, self.db_file, self.user, self.password)
            
            if result != 0:
                error_code_basica = microsip_dll.GetLastErrorCode()
                msg = f"Fallo de conexión a la BD Firebird. Código DBConnect: {result}. Error API Básica: {error_code_basica}"
                print(f"\n--- DEBUG DE CONEXIÓN FALLIDA ---\nDEBUG: Ruta usada: {self.db_file.decode('latin-1')}\n-----------------------------------\n")
                raise MicrosipAPIError(msg, api_error_code=result, api_function="DBConnect", basic_error_code=error_code_basica)

            self.is_connected = True
            
            # 2. Establecer el handle de la BD para la API de Inventarios
            result = microsip_dll.SetDBInventarios(self.db_handle)
            if result != 0:
                self._get_api_error_message(function_name="SetDBInventarios")
            
            self.microsip_connected = True
            print(f"DEBUG: Conexión con Microsip API establecida ({self.db_handle}).")

        except Exception:
            if self.is_connected:
                microsip_dll.DBDisconnect(-1)
            self.is_connected = False
            self.microsip_connected = False
            raise 

    def desconectar(self):
        """Llama a DBDisconnect(-1)."""
        if self.is_connected:
            result = microsip_dll.DBDisconnect(-1)
            if result == 0:
                self.is_connected = False
                self.microsip_connected = False
                print("DEBUG: Desconexión de Microsip API exitosa.")
            else:
                error_buffer = create_string_buffer(256)
                microsip_dll.inGetLastErrorMessage(error_buffer)
                error_message = error_buffer.value.decode('latin-1', errors='ignore')
                print(f"ADVERTENCIA: Fallo al desconectar la API. Mensaje: {error_message}")
    
    def _obtener_conteo_articulos_activos(self):
        """Ejecuta SELECT COUNT(*) y retorna el número de filas activas."""
        sql_handle_count = microsip_dll.NewSql(self.trn_handle)
        count_val = c_int(0)
        total_esperado = 0
        
        query_count = "SELECT COUNT(*) C FROM ARTICULOS WHERE ESTATUS = 'A'"
        
        try:
            result = microsip_dll.SqlQry(sql_handle_count, query_count.encode('latin-1'))
            if result != 0: self._get_api_error_message("SqlQry", "Conteo Articulos")

            result = microsip_dll.SqlExecQuery(sql_handle_count)
            if result != 0: self._get_api_error_message("SqlExecQuery", "Conteo Articulos")

            if microsip_dll.SqlNext(sql_handle_count) == 0:
                result_count = microsip_dll.SqlGetFieldAsInteger(sql_handle_count, b"C", byref(count_val))
                if result_count == 0:
                    total_esperado = count_val.value
        finally:
            microsip_dll.SqlClose(sql_handle_count)
        
        print(f"DEBUG: Conteo de artículos activos (COUNT(*)): {total_esperado}")
        return total_esperado

    def _obtener_conteo_claves_auxiliares(self):
        """Ejecuta SELECT COUNT(*) y retorna el número total de claves auxiliares."""
        sql_handle_count = microsip_dll.NewSql(self.trn_handle)
        count_val = c_int(0)
        total_esperado = 0
        
        query_count = "SELECT COUNT(*) C FROM CLAVES_ARTICULOS"
        
        try:
            result = microsip_dll.SqlQry(sql_handle_count, query_count.encode('latin-1'))
            if result != 0: self._get_api_error_message("SqlQry", "Conteo Claves")

            result = microsip_dll.SqlExecQuery(sql_handle_count)
            if result != 0: self._get_api_error_message("SqlExecQuery", "Conteo Claves")

            if microsip_dll.SqlNext(sql_handle_count) == 0:
                result_count = microsip_dll.SqlGetFieldAsInteger(sql_handle_count, b"C", byref(count_val))
                if result_count == 0:
                    total_esperado = count_val.value
        finally:
            microsip_dll.SqlClose(sql_handle_count)
        
        print(f"DEBUG: Conteo de claves auxiliares (COUNT(*)): {total_esperado}")
        return total_esperado


    # @microsip_connect <-- ELIMINADO para evitar doble decoración/desconexión
    def extraer_articulos_y_claves_msip(self):
        """
        [FUNCIÓN DE BAJO NIVEL]
        Extracción: Reúne y procesa datos de ARTICULOS y CLAVES_ARTICULOS.
        Retorna (articulos_data, claves_por_articulo, ids_microsip_activos).
        """
        
        # 0. Obtener el número de filas esperadas para Articulos (Maestro)
        total_esperado_articulos = self._obtener_conteo_articulos_activos()
        
        articulos_data = {}
        ids_microsip_activos = set()
        
        # --- 1. Extracción de ARTICULOS (Maestro) ---
        sql_handle_articulos = microsip_dll.NewSql(self.trn_handle)
        print("-> 1. Extrayendo ARTICULOS principales...") 
        
        # Usamos ORDER BY ARTICULO_ID para garantizar un orden de lectura predecible
        query_articulos = "SELECT ARTICULO_ID, NOMBRE, SEGUIMIENTO FROM ARTICULOS WHERE ESTATUS = 'A' ORDER BY ARTICULO_ID ASC"
        
        # Inicialización del contador
        articulos_procesados = 0
        imprimir_cada = 1000 
        last_processed_id = 0
        
        try:
            result = microsip_dll.SqlQry(sql_handle_articulos, query_articulos.encode('latin-1'))
            if result != 0: self._get_api_error_message("SqlQry", "Extraer Articulos")

            result = microsip_dll.SqlExecQuery(sql_handle_articulos)
            if result != 0: self._get_api_error_message("SqlExecQuery", "Extraer Articulos")

            # Lectura y procesamiento de ARTICULOS
            articulo_id_val = c_int(0)
            
            # ACOTAMOS: Limitamos el bucle al total esperado
            while microsip_dll.SqlNext(sql_handle_articulos) == 0 and articulos_procesados < total_esperado_articulos:
                
                # Lectura de ID
                result_id = microsip_dll.SqlGetFieldAsInteger(sql_handle_articulos, b"ARTICULO_ID", byref(articulo_id_val))
                
                if result_id != 0:
                    print(f"Advertencia: Fallo al leer ARTICULO_ID para el registro #{articulos_procesados + 1}, saltando. Error code: {result_id}")
                    continue

                msip_id = articulo_id_val.value
                last_processed_id = msip_id # Actualizar el último ID leído con éxito
                
                # Reporte en tiempo real
                if articulos_procesados % imprimir_cada == 0:
                    print(f"DEBUG: Procesando artículo {articulos_procesados + 1}/{total_esperado_articulos}. Último ID: {last_processed_id}", end='\r', flush=True) 
                
                ids_microsip_activos.add(msip_id)
                
                # Lectura de Opcionales
                nombre = self._read_field_as_string(sql_handle_articulos, "NOMBRE")
                seguimiento_raw = self._read_field_as_string(sql_handle_articulos, "SEGUIMIENTO")
                
                try:
                    seguimiento_int = int(seguimiento_raw)
                except ValueError:
                    seguimiento_int = 0

                articulos_data[msip_id] = {
                    'clave': "", # Se llenará en el paso 2
                    'nombre': nombre,
                    'seguimiento_tipo': SEGUIMIENTO_MAP_IN.get(seguimiento_int, 'N'),
                }
                articulos_procesados += 1
            
            # VERIFICACIÓN DE SALIDA
            if articulos_procesados >= total_esperado_articulos and total_esperado_articulos > 0:
                print(f"\nDEBUG: Límite de {total_esperado_articulos} artículos alcanzado. Deteniendo bucle preventivamente.")
            elif articulos_procesados < total_esperado_articulos:
                 print(f"\nADVERTENCIA: Bucle terminado después de {articulos_procesados} registros, esperaba {total_esperado_articulos}.")

        finally:
            microsip_dll.SqlClose(sql_handle_articulos)
            print(f"-> Artículos principales extraídos: {len(articulos_data)}. Total procesado: {articulos_procesados}. Último ID exitoso: {last_processed_id}")


        # --- 2. Extracción de CLAVES_ARTICULOS (Códigos Auxiliares) ---
        
        total_esperado_claves = self._obtener_conteo_claves_auxiliares()
        claves_por_articulo = {}
        sql_handle_claves = microsip_dll.NewSql(self.trn_handle)
        print("-> 2. Extrayendo CLAVES_ARTICULOS...")
        
        claves_procesadas = 0
        
        try:
            query_claves = "SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS"
            
            result = microsip_dll.SqlQry(sql_handle_claves, query_claves.encode('latin-1'))
            if result != 0: self._get_api_error_message("SqlQry", "Extraer Claves")
            
            result = microsip_dll.SqlExecQuery(sql_handle_claves)
            if result != 0: self._get_api_error_message("SqlExecQuery", "Extraer Claves")

            articulo_id_val = c_int(0)

            # ACOTAMOS: Limitamos el bucle
            while microsip_dll.SqlNext(sql_handle_claves) == 0 and claves_procesadas < total_esperado_claves:
                
                claves_procesadas += 1
                if claves_procesadas % imprimir_cada == 0:
                    print(f"DEBUG: Leyendo claves... Procesadas: {claves_procesadas}/{total_esperado_claves}", end='\r', flush=True)
                
                result_id = microsip_dll.SqlGetFieldAsInteger(sql_handle_claves, b"ARTICULO_ID", byref(articulo_id_val))
                clave = self._read_field_as_string(sql_handle_claves, "CLAVE_ARTICULO")
                
                if result_id == 0:
                    msip_id = articulo_id_val.value
                    
                    if msip_id in articulos_data:
                        if msip_id not in claves_por_articulo:
                            claves_por_articulo[msip_id] = []
                        claves_por_articulo[msip_id].append(clave)
                        
                        # Asignar la primera clave auxiliar encontrada como la principal si está vacía
                        if not articulos_data[msip_id]['clave']:
                            articulos_data[msip_id]['clave'] = clave
        
            if claves_procesadas < total_esperado_claves:
                 print(f"\nADVERTENCIA: Bucle de claves terminó antes de lo esperado.")

        finally:
            microsip_dll.SqlClose(sql_handle_claves)
            print(f"-> Claves auxiliares agrupadas para {len(claves_por_articulo)} artículos. Total procesadas: {claves_procesadas}")


        # ==============================================================================
        # ⚠️ DIAGNÓSTICO DE ARTÍCULOS SIN CLAVE (PROBLEMÁTICOS)
        # ==============================================================================
        articulos_sin_clave = []
        for msip_id, data in articulos_data.items():
            if not data['clave']:  # Si la clave sigue vacía después del proceso de claves
                articulos_sin_clave.append({
                    'id_microsip': msip_id,
                    'nombre': data['nombre']
                })
        
        if articulos_sin_clave:
            print(f"\n❌ ALERTA: Se encontraron {len(articulos_sin_clave)} artículos SIN CLAVE ASIGNADA.")
            print("Estos artículos son los que probablemente están fallando al guardarse en Django.")
            print("--- LISTADO DE ARTÍCULOS PROBLEMÁTICOS (Primeros 50) ---")
            print(f"{'ID MICROSIP':<15} | {'NOMBRE'}")
            print("-" * 50)
            
            for art in articulos_sin_clave[:50]: # Mostramos solo los primeros 50 para no inundar la consola
                print(f"{art['id_microsip']:<15} | {art['nombre']}")
            
            if len(articulos_sin_clave) > 50:
                print(f"... y {len(articulos_sin_clave) - 50} más.")
            print("-" * 50)
            
            # --- CORRECCIÓN AUTOMÁTICA (FALLBACK) ---
            # Asignamos MS-{ID} como clave para asegurar que se guarden
            print("🛠️ Aplicando corrección automática: Asignando 'MS-{ID}' como clave temporal...")
            for msip_id in [a['id_microsip'] for a in articulos_sin_clave]:
                articulos_data[msip_id]['clave'] = f"MS-{msip_id}"
        else:
            print("\n✅ DIAGNÓSTICO: Todos los artículos tienen clave asignada.")

        print(f"DEBUG: Catálogo extraído: {len(articulos_data)} artículos.")
        return articulos_data, claves_por_articulo, ids_microsip_activos

    def _read_field_as_string(self, sql_handle, field_name):
        """Helper para leer un campo STRING de forma segura."""
        name_bytes = field_name.encode('latin-1')
        buffer = create_string_buffer(256)
        result = microsip_dll.SqlGetFieldAsString(sql_handle, name_bytes, buffer)
        
        if result == 0:
            return buffer.value.decode('latin-1', errors='ignore').strip()
        return ""

    def diagnostico_sql(self):
        """Prueba rápida para diagnosticar si el motor SQL acepta una consulta mínima."""
        info = {}
        sql_handle = microsip_dll.NewSql(self.trn_handle)
        try:
            q = "SELECT 1 FROM RDB$DATABASE"
            info['query'] = q
            microsip_dll.SqlQry(sql_handle, q.encode('latin-1'))
            info['SqlExecQuery'] = microsip_dll.SqlExecQuery(sql_handle)
        finally:
            microsip_dll.SqlClose(sql_handle)
        return info

    @microsip_connect
    def registrar_entrada_msip(self, encabezado_data, renglones_data):
        """
        [FUNCIÓN DE BAJO NIVEL]
        Implementa la lógica completa para registrar una nueva Entrada de Inventario en Microsip.
        """
        # 1. ENCABEZADO
        print("DEBUG: Iniciando NuevaEntrada...")
        fecha_str = encabezado_data['Fecha'].encode('latin-1')
        folio_str = encabezado_data.get('Folio', '').encode('latin-1')
        desc_str = encabezado_data.get('Descripcion', '').encode('latin-1')

        result = microsip_dll.NuevaEntrada(
            c_int(encabezado_data['ConceptoInId']),
            c_int(encabezado_data['AlmacenId']),
            fecha_str,
            folio_str,
            desc_str,
            c_int(encabezado_data.get('CentroCostold', 0))
        )
        self._get_api_error_message(function_name="NuevaEntrada", bookmark="Encabezado")

        # 2. RENGLONES
        print("DEBUG: Registrando renglones...")
        for i, renglon in enumerate(renglones_data):
            articulo_id_final = renglon['ArticuloId']
            seguimiento = renglon['Seguimiento']
            articulo_nombre = renglon['Nombre']
            
            result = microsip_dll.RenglonEntrada(
                c_int(articulo_id_final),
                c_double(renglon['Unidades']),
                c_double(renglon.get('CostoUnitario', 0.0)),
                c_double(renglon.get('CostoTotal', 0.0))
            )
            self._get_api_error_message(function_name="RenglonEntrada", bookmark=f"Articulo {articulo_nombre}")

            # c. Lotes/Series
            if seguimiento == 1: # Lotes
                lotes = renglon.get('Lotes', [])
                for lote in lotes:
                    lote_clave_str = lote['ClaveLote'].encode('latin-1')
                    fecha_caducidad_str = lote['FechaCaducidad'].encode('latin-1')
                    result = microsip_dll.RenglonEntradaLotes(
                        lote_clave_str, fecha_caducidad_str, c_double(lote['Unidades'])
                    )
                    self._get_api_error_message(function_name="RenglonEntradaLotes", bookmark=f"Lote {lote['ClaveLote']}")
                    
            elif seguimiento == 2: # Series
                series = renglon.get('Series', [])
                for serie in series:
                    serie_clave_str = serie['ClaveSerie'].encode('latin-1')
                    num_consecutivos = serie.get('NumConsecutivos', 1)
                    result = microsip_dll.RenglonEntradaSeries(serie_clave_str, c_int(num_consecutivos))
                    self._get_api_error_message(function_name="RenglonEntradaSeries", bookmark=f"Serie {serie['ClaveSerie']}")

        # 3. APLICACIÓN
        print("DEBUG: Aplicando entrada...")
        result = microsip_dll.AplicaEntrada()
        self._get_api_error_message(function_name="AplicaEntrada", bookmark="Finalización")

        print("DEBUG: ¡Entrada de inventario registrada y aplicada con éxito!")
        return True