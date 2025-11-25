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
        # La bandera 'microsip_connected' garantiza que no se intente una doble conexión
        if not self.microsip_connected:
            self.conectar()
            
        try:
            # 2. Ejecutar la función decorada
            result = func(self, *args, **kwargs)
            return result
        
        except MicrosipAPIError as e:
            # Si hay un error al registrar un documento, siempre se aborta la transacción
            # antes de relanzar la excepción para que el llamador pueda manejarla.
            try:
                if self.is_connected:
                    microsip_dll.AbortaDoctoInventarios()
                    print(f"DEBUG: Transacción de Microsip abortada después del error: {e}")
            except Exception as abort_e:
                print(f"ADVERTENCIA: Fallo al intentar abortar la transacción: {abort_e}")
            
            # Re-lanzar la excepción limpia
            raise e
            
        finally:
            # 3. Desconectar (Siempre se intenta, incluso si falla la ejecución)
            if self.microsip_connected:
                self.desconectar()

    return wrapper


# NOTA: Debemos declarar la función GetLastErrorCode de la API Básica aquí, 
# ya que solo se declaró la inGetLastErrorMessage (API Inventarios) en el archivo de declaraciones.
try:
    microsip_dll.GetLastErrorCode.restype = c_int
except AttributeError:
    pass

# Mapeo de valores de SEGUIMIENTO (Microsip Integer) a Django Char (Solo para Extracción)
SEGUIMIENTO_MAP_IN = {
    0: 'N',  # Ninguno
    1: 'L',  # Lotes
    2: 'S',  # Series
}

class MicrosipConnectionBase:
    """
    Clase base que gestiona la conexión de bajo nivel, los handles y la comunicación
    con la ApiMicrosip.dll. Mantiene los métodos de diagnóstico útiles para depuración futura.
    """
    def __init__(self):
        # Lee la configuración del diccionario MICROSIP_CONFIG
        try:
            config = settings.MICROSIP_CONFIG
        except AttributeError:
             raise ImproperlyConfigured("La configuración MICROSIP_CONFIG no está definida en settings.py.")

        # Handles internos de conexión
        self.db_handle = microsip_dll.NewDB()  # Handle de la BD
        
        # Transacción Snapshot (Read-Only)
        self.trn_handle = microsip_dll.NewTrn(self.db_handle, 0) 
        
        # self.sql_handle NO se inicializa aquí, se crea y destruye en cada método de consulta

        # Parámetros LEÍDOS DE SETTINGS y codificados en latin-1 (para PChar)
        self.db_file = config['DB_FILE'].encode('latin-1')
        self.user = config['USER'].encode('latin-1')
        self.password = config['PASSWORD'].encode('latin-1')
        
        self.is_connected = False
        self.microsip_connected = False

    def _get_api_error_message(self, bookmark="", function_name=""):
        """
        Recupera el mensaje de error de la API y lo decodifica de 'latin-1',
        y lanza una excepción MicrosipAPIError si el código no es 0.
        """
        error_buffer = create_string_buffer(256)
        error_code = microsip_dll.inGetLastErrorMessage(error_buffer) # Código de la API especializada (Inventarios)
        basic_error_code = microsip_dll.GetLastErrorCode() # Código de la API Básica
        error_message = error_buffer.value.decode('latin-1', errors='ignore').strip()

        if error_code != 0:
            full_message = f"Error en {function_name} ({bookmark}). Código: {error_code}. Mensaje: {error_message}"
            raise MicrosipAPIError(
                full_message, 
                api_error_code=error_code,
                api_function=function_name,
                basic_error_code=basic_error_code
            )
        return None # Devuelve None si no hay error

    def conectar(self):
        """Establece la conexión a la BD Microsip e inicia la transacción."""
        try:
            # Deshabilitar excepciones de sistema operativo
            microsip_dll.inSetErrorHandling(0, 0)
            
            # 1. Conexión a la BD
            result = microsip_dll.DBConnect(self.db_handle, self.db_file, self.user, self.password)
            
            if result != 0:
                # Usar GetLastErrorCode de la API Básica para diagnóstico de conexión
                error_code_basica = microsip_dll.GetLastErrorCode() 
                
                # No podemos usar inGetLastErrorMessage porque falló DBConnect (API Básica), 
                # así que lanzamos un error de conexión más directo.
                msg = f"Fallo de conexión a la BD Firebird. Código DBConnect: {result}. Error API Básica: {error_code_basica}"
                
                # Debug de conexión fallida
                print(f"\n--- DEBUG DE CONEXIÓN FALLIDA ---")
                print(f"DEBUG: DBConnect retornó código interno: {result}")
                print(f"DEBUG: API Básica FLastErrorCode: {error_code_basica}")
                print(f"DEBUG: Ruta usada: {self.db_file.decode('latin-1')}")
                print(f"-----------------------------------\n")
                
                raise MicrosipAPIError(msg, api_error_code=result, api_function="DBConnect", basic_error_code=error_code_basica)

            self.is_connected = True
            
            # 2. Establecer el handle de la BD para la API de Inventarios (CRÍTICO)
            # En una aplicación real, deberías tener un método SetDB por cada módulo que uses.
            # Aquí asumimos que siempre se necesita Inventarios.
            result = microsip_dll.SetDBInventarios(self.db_handle)
            if result != 0:
                self._get_api_error_message(function_name="SetDBInventarios") # Esto lanzará el error
            
            # *** NOTA: Aquí se incluiría la conexión a METADATOS y ChecaCompatibilidad si fuera CRÍTICO en cada llamada.
            # Por simplicidad y rendimiento, a menudo se hace la compatibilidad solo una vez al iniciar el servidor
            # o en el comando de sincronización.
            
            self.microsip_connected = True
            print(f"DEBUG: Conexión con Microsip API establecida ({self.db_handle}).")

        except Exception as e:
            # Asegurar la desconexión si falló la configuración después de DBConnect
            if self.is_connected:
                microsip_dll.DBDisconnect(-1)
            self.is_connected = False
            self.microsip_connected = False
            raise 

    def desconectar(self):
        """Llama a DBDisconnect(-1) para liberar la licencia y recursos."""
        if self.is_connected:
            result = microsip_dll.DBDisconnect(-1)
            if result == 0:
                self.is_connected = False
                self.microsip_connected = False
                print("DEBUG: Desconexión de Microsip API exitosa.")
            else:
                # A diferencia de conectar, solo advertimos si falla la desconexión, es menos crítico
                # (aunque sí puede dejar la licencia bloqueada).
                error_buffer = create_string_buffer(256)
                microsip_dll.inGetLastErrorMessage(error_buffer)
                error_message = error_buffer.value.decode('latin-1', errors='ignore')
                print(f"ADVERTENCIA: Fallo al desconectar la API. Mensaje: {error_message}")
    
    def _obtener_conteo_articulos_activos(self):
        """[NUEVA FUNCIÓN] Ejecuta SELECT COUNT(*) y retorna el número de filas activas."""
        sql_handle_count = microsip_dll.NewSql(self.trn_handle)
        count_val = c_int(0)
        total_esperado = 0
        
        query_count = "SELECT COUNT(*) FROM ARTICULOS WHERE ESTATUS = 'A'"
        
        try:
            result = microsip_dll.SqlQry(sql_handle_count, query_count.encode('latin-1'))
            if result != 0: self._get_api_error_message("SqlQry", "Conteo Articulos")

            result = microsip_dll.SqlExecQuery(sql_handle_count)
            if result != 0: self._get_api_error_message("SqlExecQuery", "Conteo Articulos")

            # Solo hay un registro con un campo, lo leemos
            if microsip_dll.SqlNext(sql_handle_count) == 0:
                result_count = microsip_dll.SqlGetFieldAsInteger(sql_handle_count, b"COUNT", byref(count_val))
                if result_count == 0:
                    total_esperado = count_val.value
        
        finally:
            microsip_dll.SqlClose(sql_handle_count)
        
        if total_esperado == 0:
             # Si el conteo es 0, chequeamos si la tabla ARTICULOS existe, pero para evitar complejidad asumimos que existe 
             # y simplemente reportamos 0 artículos.
             print("ADVERTENCIA: El conteo de artículos activos retornó 0 o hubo un fallo silencioso.")

        print(f"DEBUG: Conteo de artículos activos (COUNT(*)): {total_esperado}")
        return total_esperado


    @microsip_connect
    def extraer_articulos_y_claves_msip(self):
        """
        [FUNCIÓN DE BAJO NIVEL]
        Extracción: Reúne y procesa datos de ARTICULOS y CLAVES_ARTICULOS.
        Retorna (articulos_data, claves_por_articulo, ids_microsip_activos).
        """
        
        # 0. Obtener el número de filas esperadas para verificar la integridad
        total_esperado = self._obtener_conteo_articulos_activos()
        
        articulos_data = {}
        ids_microsip_activos = set()
        
        # --- 1. Extracción de ARTICULOS (Maestro) ---
        sql_handle_articulos = microsip_dll.NewSql(self.trn_handle) # Handle aislado 1
        print("-> 1. Extrayendo ARTICULOS principales...") 
        
        # Usamos ORDER BY ARTICULO_ID para garantizar un orden de lectura predecible
        # y así diagnosticar el punto de falla (siempre el último, como mencionaste).
        query_articulos = "SELECT ARTICULO_ID, NOMBRE, SEGUIMIENTO FROM ARTICULOS WHERE ESTATUS = 'A' ORDER BY ARTICULO_ID ASC"
        
        # Inicialización del contador para el reporte en tiempo real
        articulos_procesados = 0
        imprimir_cada = 1000 # Reportar el progreso cada 1000 registros
        
        # Variable para almacenar el último ID procesado con éxito
        last_processed_id = 0
        
        try:
            
            result = microsip_dll.SqlQry(sql_handle_articulos, query_articulos.encode('latin-1'))
            if result != 0: self._get_api_error_message("SqlQry", "Extraer Articulos")

            result = microsip_dll.SqlExecQuery(sql_handle_articulos)
            if result != 0: self._get_api_error_message("SqlExecQuery", "Extraer Articulos")

            # Lectura y procesamiento de ARTICULOS
            articulo_id_val = c_int(0)
            
            # AHORA limitamos el bucle a total_esperado para evitar bucles infinitos 
            # en caso de que el cursor sea el problema.
            while microsip_dll.SqlNext(sql_handle_articulos) == 0 and articulos_procesados < total_esperado:
                
                # Lectura de ID (CRÍTICO)
                result_id = microsip_dll.SqlGetFieldAsInteger(sql_handle_articulos, b"ARTICULO_ID", byref(articulo_id_val))
                
                if result_id != 0:
                    print(f"Advertencia: Fallo al leer ARTICULO_ID para el registro #{articulos_procesados + 1}, saltando. Error code: {result_id}")
                    # Como no pudimos leer el ID, salimos de esta iteración.
                    continue

                msip_id = articulo_id_val.value
                
                # *** LOGGING CRÍTICO Y PUNTO DE FALLA ***
                last_processed_id = msip_id # Actualizar el último ID leído con éxito
                
                # Reporte en tiempo real
                if articulos_procesados % imprimir_cada == 0:
                    print(f"DEBUG: Procesando artículo {articulos_procesados + 1}/{total_esperado}. Último ID: {last_processed_id}", end='\r', flush=True) 
                # ***********************************
                
                ids_microsip_activos.add(msip_id)
                
                # Lectura de Opcionales (Usa el helper para robustez)
                nombre = self._read_field_as_string(sql_handle_articulos, "NOMBRE")
                seguimiento_raw = self._read_field_as_string(sql_handle_articulos, "SEGUIMIENTO")
                
                try:
                    seguimiento_int = int(seguimiento_raw)
                except ValueError:
                    seguimiento_int = 0

                articulos_data[msip_id] = {
                    # La clave se inicializa vacía y se llenará en el paso 2 con la primera clave auxiliar.
                    'clave': "", 
                    'nombre': nombre,
                    'seguimiento_tipo': SEGUIMIENTO_MAP_IN.get(seguimiento_int, 'N'),
                }
                articulos_procesados += 1 # Contador interno de artículos REALMENTE procesados.
            
            
            # ----------------------------------------------------
            # VERIFICACIÓN DE SALIDA (Para diagnóstico)
            # ----------------------------------------------------
            if articulos_procesados >= total_esperado and total_esperado > 0:
                print(f"\nDEBUG: Límite de {total_esperado} artículos alcanzado. Deteniendo bucle preventivamente.")
            elif articulos_procesados < total_esperado:
                 print(f"\nADVERTENCIA: Bucle terminado después de {articulos_procesados} registros, esperaba {total_esperado}.")
                 # Aquí podemos intentar verificar el estado de EOF y el código de error
                 error_check = self._get_api_error_message(function_name="SqlNext", bookmark="Salida prematura") 
                 if error_check:
                     print(f"DEBUG: El bucle terminó debido a un error de API: {error_check}")


        finally:
            microsip_dll.SqlClose(sql_handle_articulos) # Cierra y libera handle 1
            # Línea final para asegurar que se vea el conteo total
            print(f"-> Artículos principales extraídos: {len(articulos_data)}. Total procesado: {articulos_procesados}. Último ID exitoso: {last_processed_id}")


        # --- 2. Extracción de CLAVES_ARTICULOS (Códigos Auxiliares) ---
        claves_por_articulo = {}
        sql_handle_claves = microsip_dll.NewSql(self.trn_handle) # Handle aislado 2
        print("-> 2. Extrayendo CLAVES_ARTICULOS...")
        
        # Reiniciar contador para el reporte de claves auxiliares
        total_leidos = 0
        
        try:
            query_claves = "SELECT ARTICULO_ID, CLAVE_ARTICULO FROM CLAVES_ARTICULOS"
            
            result = microsip_dll.SqlQry(sql_handle_claves, query_claves.encode('latin-1'))
            if result != 0: self._get_api_error_message("SqlQry", "Extraer Claves")
            
            result = microsip_dll.SqlExecQuery(sql_handle_claves)
            if result != 0: self._get_api_error_message("SqlExecQuery", "Extraer Claves")

            articulo_id_val = c_int(0)

            while microsip_dll.SqlNext(sql_handle_claves) == 0:
                
                # --- LÓGICA DE CONTEO Y REPORTE EN TIEMPO REAL ---
                total_leidos += 1
                if total_leidos % imprimir_cada == 0:
                    print(f"DEBUG: Leyendo claves... Iteraciones leídas: {total_leidos}", end='\r', flush=True)
                # -------------------------------------------------
                
                # Lectura del ID (Necesario para mapeo)
                result_id = microsip_dll.SqlGetFieldAsInteger(sql_handle_claves, b"ARTICULO_ID", byref(articulo_id_val))
                
                # Lectura de la clave auxiliar
                clave = self._read_field_as_string(sql_handle_claves, "CLAVE_ARTICULO")
                
                if result_id == 0:
                    msip_id = articulo_id_val.value
                    
                    if msip_id in articulos_data: # Solo si el artículo maestro fue extraído
                        if msip_id not in claves_por_articulo:
                            claves_por_articulo[msip_id] = []
                        claves_por_articulo[msip_id].append(clave)
                        
                        # LÓGICA DE SINCRONIZACIÓN: Usar la primera clave auxiliar como la clave principal del Articulo
                        if not articulos_data[msip_id]['clave']:
                            articulos_data[msip_id]['clave'] = clave
        
        finally:
            microsip_dll.SqlClose(sql_handle_claves) # Cierra y libera handle 2
            # Línea final para asegurar que se vea el conteo total
            print(f"-> Claves auxiliares agrupadas para {len(claves_por_articulo)} artículos. Iteraciones leídas: {total_leidos}")


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

    # Las funciones de diagnóstico se mantienen igual...
    def diagnostico_sql(self):
        """[MÉTODO DE UTILIDAD] Prueba rápida para diagnosticar si el motor SQL acepta una consulta mínima."""
        # ... (código omitido por brevedad)
        pass

    @microsip_connect
    def registrar_entrada_msip(self, encabezado_data, renglones_data):
        """
        [FUNCIÓN DE BAJO NIVEL]
        Implementa la lógica completa para registrar una nueva Entrada de Inventario en Microsip.
        Recibe datos limpios y mapeados de la capa superior.
        """
        # Ya está conectada por el decorador, se puede proceder
            
        # El decorador maneja el try/except/finally de conexión/desconexión
        # Solo necesitamos el try/except del documento para el AbortaDoctoInventarios si falla en el medio.
        
        # 1. ENCABEZADO: NuevaEntrada
        print("DEBUG: Iniciando NuevaEntrada...")
        
        # Codificación de PChar
        fecha_str = encabezado_data['Fecha'].encode('latin-1') # D/M/A
        folio_str = encabezado_data.get('Folio', '').encode('latin-1')
        desc_str = encabezado_data.get('Descripcion', '').encode('latin-1')

        # Se usa self._get_api_error_message después de cada llamada que puede fallar
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
            
            # b. RenglonEntrada
            result = microsip_dll.RenglonEntrada(
                c_int(articulo_id_final),
                c_double(renglon['Unidades']),
                c_double(renglon.get('CostoUnitario', 0.0)),
                c_double(renglon.get('CostoTotal', 0.0))
            )
            self._get_api_error_message(function_name="RenglonEntrada", bookmark=f"Articulo {articulo_nombre}")

            # c. Lotes/Series (Solo si seguimiento es 1 o 2)
            if seguimiento == 1: # Lotes
                lotes = renglon.get('Lotes', [])
                if not lotes:
                    print("DEBUG: Advertencia: Artículo por Lotes sin datos de lote, se asignará 'SIN LOTE'.")
                
                for lote in lotes:
                    lote_clave_str = lote['ClaveLote'].encode('latin-1')
                    fecha_caducidad_str = lote['FechaCaducidad'].encode('latin-1') # D/M/A
                    
                    result = microsip_dll.RenglonEntradaLotes(
                        lote_clave_str,
                        fecha_caducidad_str,
                        c_double(lote['Unidades'])
                    )
                    self._get_api_error_message(function_name="RenglonEntradaLotes", bookmark=f"Lote {lote['ClaveLote']}")
                    
            elif seguimiento == 2: # Series
                series = renglon.get('Series', [])
                if not series:
                    print("DEBUG: Advertencia: Artículo por Series sin datos de serie, se asignará 'SIN SERIE'.")
                    
                for serie in series:
                    serie_clave_str = serie['ClaveSerie'].encode('latin-1')
                    num_consecutivos = serie.get('NumConsecutivos', 1)
                    
                    result = microsip_dll.RenglonEntradaSeries(
                        serie_clave_str,
                        c_int(num_consecutivos)
                    )
                    self._get_api_error_message(function_name="RenglonEntradaSeries", bookmark=f"Serie {serie['ClaveSerie']}")


        # 3. APLICACIÓN
        print("DEBUG: Aplicando entrada...")
        result = microsip_dll.AplicaEntrada()
        self._get_api_error_message(function_name="AplicaEntrada", bookmark="Finalización")

        print("DEBUG: ¡Entrada de inventario registrada y aplicada con éxito!")
        return True