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
    
    NOTA: Las funciones de LECTURA masiva han sido eliminadas de aquí porque
    ahora se realizan vía SQL Directo (FDB) en los servicios de Sync.
    Esta clase se conserva para Gestión de Conexión y Escritura (Transactions).
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
        [FUNCIÓN DE BAJO NIVEL - CONSERVADA PARA ESCALABILIDAD]
        Implementa la lógica completa para registrar una nueva Entrada de Inventario en Microsip.
        Esta función es vital para futuras funcionalidades de escritura (ej. enviar conteos a Microsip).
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