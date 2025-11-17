# tu_app/microsip_service.py - Funciones Esenciales
from ctypes import c_int, c_char_p, c_double, byref, create_string_buffer
from datetime import datetime
from django.conf import settings # ¡Nueva Importación!

# Importa las declaraciones de la DLL.
from microsip_api import microsip_dll

class MicrosipService:
    # Constructor modificado para leer de settings
    def __init__(self):
        # Lee la configuración del diccionario MICROSIP_CONFIG
        config = settings.MICROSIP_CONFIG

        # Handles internos de conexión
        self.db_handle = microsip_dll.NewDB()  # Handle de la BD
        
        # Tipo de transacción 3 (ReadCommittedNoWait) para consultas SQL auxiliares.
        self.trn_handle = microsip_dll.NewTrn(self.db_handle, 3) 
        self.sql_handle = microsip_dll.NewSql(self.trn_handle) # Handle para consultas SQL

        # Parámetros LEÍDOS DE SETTINGS y codificados en latin-1 (para PChar)
        self.db_file = config['DB_FILE'].encode('latin-1')
        self.user = config['USER'].encode('latin-1')
        self.password = config['PASSWORD'].encode('latin-1')
        
        # Estado de la conexión
        self.is_connected = False
        self.microsip_connected = False

    def _get_api_error_message(self, bookmark=""):
        """Recupera el mensaje de error de la API y lo decodifica de 'latin-1'."""
        # Creamos un buffer de 256 bytes (suficiente para la mayoría de mensajes de error)
        error_buffer = create_string_buffer(256)
        
        # inGetLastErrorMessage llena el buffer y regresa el código de error
        error_code = microsip_dll.inGetLastErrorMessage(error_buffer)
        
        # El buffer contiene el byte string terminado en nulo
        error_message_bytes = error_buffer.value
        
        # Decodificamos de latin-1
        error_message = error_message_bytes.decode('latin-1', errors='ignore')

        if error_code != 0:
            return f"ERROR #{error_code} en Microsip API ({bookmark}): {error_message}"
        return None

    def conectar(self):
        """Establece la conexión a la BD Microsip y Metadatos."""
        try:
            # 1. Configurar manejo de errores para la API de Inventarios (inSetErrorHandling(0, 0))
            # No levantar excepciones, solo devolver código de error.
            microsip_dll.inSetErrorHandling(0, 0)
            
            # 2. Conexión a la BD
            result = microsip_dll.DBConnect(self.db_handle, self.db_file, self.user, self.password)
            if result != 0:
                error = self._get_api_error_message("DBConnect")
                raise Exception(f"Fallo de conexión a la BD: {error}")
            
            self.is_connected = True

            # 3. Establecer el handle de la BD para la API de Inventarios
            result = microsip_dll.SetDBInventarios(self.db_handle)
            if result != 0:
                error = self._get_api_error_message("SetDBInventarios")
                microsip_dll.DBDisconnect(-1)
                raise Exception(f"Fallo al establecer DB Inventarios: {error}")
            
            self.microsip_connected = True
            print("Conexión con Microsip API establecida con éxito.")

        except Exception as e:
            print(f"Error fatal durante la conexión: {e}")
            self.is_connected = False
            self.microsip_connected = False
            # Opcionalmente, lanzar o manejar el error
            raise

    def desconectar(self):
        """Llama a DBDisconnect(-1) para liberar la licencia y recursos."""
        if self.is_connected:
            # -1 desconecta todas las bases de datos y libera la licencia.
            result = microsip_dll.DBDisconnect(-1)
            error = self._get_api_error_message("DBDisconnect")
            
            if result == 0:
                self.is_connected = False
                self.microsip_connected = False
                print("Desconexión de Microsip API exitosa.")
            else:
                print(f"Advertencia durante la desconexión: {error}")

    def _obtener_datos_articulo(self, campo_busqueda, valor_busqueda):
        """
        Busca un artículo por cualquier campo (ID, código de barras, clave de proveedor, etc.)
        en la BD Microsip usando SqlQry.
        Devuelve un diccionario con los datos críticos (ARTICULO_ID, SEGUIMIENTO).
        Devuelve None si no encuentra el artículo.
        """
        if not self.microsip_connected:
            raise Exception("Microsip API no conectada. Conecte primero.")

        # Construcción dinámica de la consulta para buscar por campo auxiliar.
        query = (
            "SELECT a.ARTICULO_ID, a.NOMBRE, a.ES_ALMACENABLE, a.ES_JUEGO, a.SEGUIMIENTO "
            f"FROM ARTICULOS a WHERE a.{campo_busqueda} = :VALOR"
        )
        
        # 1. Establecer el query
        result = microsip_dll.SqlQry(self.sql_handle, query.encode('latin-1'))
        if result != 0:
            error = self._get_api_error_message("SqlQry (Busqueda Articulo)")
            raise Exception(f"Error al establecer el query: {error}")

        # 2. Asignar el parámetro PChar usando SqlSetParamAsString 
        param_name_bytes = b"VALOR"
        param_value_bytes = str(valor_busqueda).encode('latin-1')
        
        result = microsip_dll.SqlSetParamAsString(
            self.sql_handle, 
            param_name_bytes, 
            param_value_bytes
        )
        if result != 0:
            error = self._get_api_error_message("SqlSetParamAsString (Busqueda Articulo)")
            microsip_dll.SqlClose(self.sql_handle)
            raise Exception(f"Error al asignar parámetro de búsqueda: {error}")
        
        # 3. Ejecutar el query
        result = microsip_dll.SqlExecQuery(self.sql_handle)
        if result != 0:
            error = self._get_api_error_message("SqlExecQuery (Busqueda Articulo)")
            microsip_dll.SqlClose(self.sql_handle)
            raise Exception(f"Error al ejecutar consulta: {error}")

        # 4. Leer el primer registro
        articulo_data = None
        if microsip_dll.SqlNext(self.sql_handle) == 0: # Si hay un registro
            
            # Recuperar ARTICULO_ID (Integer)
            articulo_id_val = c_int(0)
            result_id = microsip_dll.SqlGetFieldAsInteger(
                self.sql_handle, 
                b"ARTICULO_ID", 
                byref(articulo_id_val)
            )

            # Recuperar SEGUIMIENTO (Integer)
            seguimiento_val = c_int(0)
            result_seg = microsip_dll.SqlGetFieldAsInteger(
                self.sql_handle, 
                b"SEGUIMIENTO", 
                byref(seguimiento_val)
            )
            
            if result_id == 0 and result_seg == 0:
                articulo_data = {
                    "ARTICULO_ID": articulo_id_val.value,
                    "SEGUIMIENTO": seguimiento_val.value
                }
            else:
                error = self._get_api_error_message("SqlGetFieldAsInteger (ID/SEGUIMIENTO)")
                microsip_dll.SqlClose(self.sql_handle)
                raise Exception(f"Error al leer campos ID/SEGUIMIENTO: {error}")

        microsip_dll.SqlClose(self.sql_handle)
        return articulo_data # Devuelve el dict o None
    
    def _ejecutar_consulta_articulo(self, articulo_id):
        """Función de compatibilidad para el ejemplo, ahora obsoleta si se usa el modelo Articulo."""
        datos = self._obtener_datos_articulo("ARTICULO_ID", articulo_id)
        return datos['SEGUIMIENTO'] if datos else None


    def registrar_entrada(self, encabezado_data, renglones_data):
        """
        Implementa la lógica completa para registrar una nueva Entrada de Inventario.
        :param encabezado_data: Diccionario con ConceptoInId, AlmacenId, Fecha, Folio, Descripcion, CentroCostold.
        :param renglones_data: Lista de diccionarios con Articulold, Unidades, CostoUnitario, CostoTotal, y opcionalmente Lotes/Series.
        """
        if not self.microsip_connected:
            raise Exception("Microsip API no conectada. Conecte primero.")
            
        try:
            # 1. ENCABEZADO: NuevaEntrada
            print("Iniciando NuevaEntrada...")
            
            # Codificación de PChar
            fecha_str = encabezado_data['Fecha'].encode('latin-1') # D/M/A
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
            
            if result != 0:
                error = self._get_api_error_message("NuevaEntrada")
                raise Exception(f"Fallo al registrar encabezado: {error}")

            # 2. RENGLONES
            print("Registrando renglones...")
            for i, renglon in enumerate(renglones_data):
                # NOTA DE DISEÑO CRÍTICA:
                # En producción, NO USAR _obtener_datos_articulo aquí.
                # Se deben obtener los datos del modelo Articulo de Django (Articulo.objects.get(...))
                # para la UX rápida. Aquí se usa el mock/consulta directa por simplicidad del ejemplo.
                
                clave_busqueda = renglon['ArticuloId']
                
                # EJEMPLO DE LÓGICA DE PRODUCCIÓN (Comentar si no se usa el mock):
                # try:
                #     articulo_cache = Articulo.objects.get(codigo_barras=clave_busqueda)
                #     articulo_id_final = articulo_cache.articulo_id_msip
                #     seguimiento = {'N': 0, 'L': 1, 'S': 2}[articulo_cache.seguimiento_tipo]
                # except Articulo.DoesNotExist:
                #     raise Exception(f"Artículo con clave {clave_busqueda} no encontrado en caché local.")
                
                # --- INICIO DEL MOCK/CONSULTA DIRECTA ---
                datos_articulo = self._obtener_datos_articulo("ARTICULO_ID", clave_busqueda)
                
                if not datos_articulo:
                    raise Exception(f"Artículo con ID/Clave {clave_busqueda} no encontrado.")

                articulo_id_final = datos_articulo['ARTICULO_ID']
                seguimiento = datos_articulo['SEGUIMIENTO']
                # --- FIN DEL MOCK/CONSULTA DIRECTA ---
                

                print(f"  Artículo {articulo_id_final} (Clave: {clave_busqueda}) tiene seguimiento: {seguimiento}") # 0=Sin, 1=Lote, 2=Serie

                # b. RenglonEntrada usa el ID PRIMARIO (articulo_id_final)
                result = microsip_dll.RenglonEntrada(
                    c_int(articulo_id_final),
                    c_double(renglon['Unidades']),
                    c_double(renglon.get('CostoUnitario', 0.0)),
                    c_double(renglon.get('CostoTotal', 0.0))
                )
                
                if result != 0:
                    error = self._get_api_error_message(f"RenglonEntrada (Art. {articulo_id_final})")
                    raise Exception(f"Fallo al registrar renglón {i+1}: {error}")

                # c. Lotes/Series (Solo si seguimiento es 1 o 2)
                if seguimiento == 1: # Lotes
                    lotes = renglon.get('Lotes', [])
                    if not lotes:
                        print("    Advertencia: Artículo por Lotes sin datos de lote, se asignará 'SIN LOTE'.")
                    
                    for lote in lotes:
                        lote_clave_str = lote['ClaveLote'].encode('latin-1')
                        fecha_caducidad_str = lote['FechaCaducidad'].encode('latin-1') # D/M/A
                        
                        result = microsip_dll.RenglonEntradaLotes(
                            lote_clave_str,
                            fecha_caducidad_str,
                            c_double(lote['Unidades'])
                        )
                        if result != 0:
                            error = self._get_api_error_message(f"RenglonEntradaLotes (Lote {lote['ClaveLote']})")
                            raise Exception(f"Fallo al registrar lote {lote['ClaveLote']}: {error}")
                        print(f"    Lote '{lote['ClaveLote']}' registrado con éxito.")
                        
                elif seguimiento == 2: # Series
                    series = renglon.get('Series', [])
                    if not series:
                        print("    Advertencia: Artículo por Series sin datos de serie, se asignará 'SIN SERIE'.")
                        
                    for serie in series:
                        serie_clave_str = serie['ClaveSerie'].encode('latin-1')
                        num_consecutivos = serie.get('NumConsecutivos', 1)
                        
                        result = microsip_dll.RenglonEntradaSeries(
                            serie_clave_str,
                            c_int(num_consecutivos)
                        )
                        if result != 0:
                            error = self._get_api_error_message(f"RenglonEntradaSeries (Serie {serie['ClaveSerie']})")
                            raise Exception(f"Fallo al registrar serie {serie['ClaveSerie']}: {error}")
                        print(f"    Serie '{serie['ClaveSerie']}' ({num_consecutivos} consec.) registrada con éxito.")

            # 3. APLICACIÓN
            print("Aplicando entrada...")
            result = microsip_dll.AplicaEntrada()
            
            if result != 0:
                error = self._get_api_error_message("AplicaEntrada")
                raise Exception(f"Fallo al aplicar la entrada: {error}")

            print("¡Entrada de inventario registrada y aplicada con éxito!")
            return True

        except Exception as e:
            # En caso de cualquier error, abortar el documento
            microsip_dll.AbortaDoctoInventarios()
            print(f"ERROR: La transacción ha sido abortada. Causa: {e}")
            return False
