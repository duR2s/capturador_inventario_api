from ctypes import c_int, c_char_p, c_double, windll, create_string_buffer

# --- CONFIGURACIÓN DE LA DLL (ApiMicrosip.dll) ---
# Se asume que la DLL está accesible en el PATH o en la carpeta del script/ejecutable.
try:
    microsip_dll = windll.LoadLibrary("ApiMicrosip.dll")
except OSError as e:
    print(f"Error al cargar la DLL: {e}. Asegúrate de que estás usando Python 32-bit (x86) y que la DLL está accesible.")
    raise

# --- API BÁSICA (Para manejo de errores) ---

# inSetErrorHandling(ExceptionOnError, MessageOnException: Integer); stdcall;
# La función de Inventarios es inSetErrorHandling (de la API Inventarios, no la básica SetErrorHandling)
microsip_dll.inSetErrorHandling.argtypes = [c_int, c_int]
microsip_dll.inSetErrorHandling.restype = c_int

# inGetLastErrorMessage (ErrorMessage: PChar): Integer; stdcall;
# Nota: La Api Inventarios usa inGetLastErrorMessage
microsip_dll.inGetLastErrorMessage.argtypes = [c_char_p]
microsip_dll.inGetLastErrorMessage.restype = c_int

# DBDisconnect(DBHandle: Integer): Integer; stdcall;
microsip_dll.DBDisconnect.argtypes = [c_int]
microsip_dll.DBDisconnect.restype = c_int

# DBConnect(DBHandle: Integer; DatabaseName, UserName, Password: PChar): Integer; stdcall;
microsip_dll.DBConnect.argtypes = [c_int, c_char_p, c_char_p, c_char_p]
microsip_dll.DBConnect.restype = c_int

# NewDB: Integer; stdcall; (Se asume que NewDB y NewTrn están en la DLL si los usa DBConnect)
microsip_dll.NewDB.restype = c_int
microsip_dll.NewTrn.argtypes = [c_int, c_int]
microsip_dll.NewTrn.restype = c_int

# SetDBInventarios (DBHandle: Integer): Integer; stdcall;
microsip_dll.SetDBInventarios.argtypes = [c_int]
microsip_dll.SetDBInventarios.restype = c_int

# SqlQry (SqlHandle: Integer; Query: PChar): Integer; stdcall;
microsip_dll.SqlQry.argtypes = [c_int, c_char_p]
microsip_dll.SqlQry.restype = c_int

# SqlExecQuery (SqlHandle: Integer): Integer; stdcall;
microsip_dll.SqlExecQuery.argtypes = [c_int]
microsip_dll.SqlExecQuery.restype = c_int

# SqlNext (SqlHandle: Integer): Integer; stdcall;
microsip_dll.SqlNext.argtypes = [c_int]
microsip_dll.SqlNext.restype = c_int

# SqlGetFieldAsInteger (SqlHandle: Integer; FieldName: PChar; Var FieldValue: Integer): Integer; stdcall;
microsip_dll.SqlGetFieldAsInteger.argtypes = [c_int, c_char_p, c_int]
microsip_dll.SqlGetFieldAsInteger.restype = c_int

# NewSql (TrnHandle: Integer): Integer; stdcall;
microsip_dll.NewSql.argtypes = [c_int]
microsip_dll.NewSql.restype = c_int

# SqlClose (SqlHandle: Integer): Integer; stdcall;
microsip_dll.SqlClose.argtypes = [c_int]
microsip_dll.SqlClose.restype = c_int

# **NUEVA DECLARACIÓN NECESARIA para la búsqueda genérica**
# SqlSetParamAsString (SqlHandle: Integer; ParamName, ParamValue: PChar): Integer; stdcall;
microsip_dll.SqlSetParamAsString.argtypes = [c_int, c_char_p, c_char_p]
microsip_dll.SqlSetParamAsString.restype = c_int

# --- API INVENTARIOS (Funciones de Entrada) ---

# NuevaEntrada(ConceptoInId, AlmacenId, Fecha, Folio, Descripcion, CentroCostold)
microsip_dll.NuevaEntrada.argtypes = [
    c_int, c_int, c_char_p, c_char_p, c_char_p, c_int
]
microsip_dll.NuevaEntrada.restype = c_int

# RenglonEntrada(Articulold, Unidades, CostoUnitario, CostoTotal)
microsip_dll.RenglonEntrada.argtypes = [
    c_int, c_double, c_double, c_double
]
microsip_dll.RenglonEntrada.restype = c_int

# RenglonEntradaLotes (ClaveLote, FechaCaducidad: PChar; Unidades: Double): Integer; stdcall;
microsip_dll.RenglonEntradaLotes.argtypes = [
    c_char_p, c_char_p, c_double
]
microsip_dll.RenglonEntradaLotes.restype = c_int

# RenglonEntradaSeries (ClaveSerie: PChar; NumConsecutivos: Integer): Integer; stdcall;
microsip_dll.RenglonEntradaSeries.argtypes = [
    c_char_p, c_int
]
microsip_dll.RenglonEntradaSeries.restype = c_int

# AplicaEntrada: Integer; stdcall;
microsip_dll.AplicaEntrada.restype = c_int

# AbortaDoctoInventarios: stdcall;
microsip_dll.AbortaDoctoInventarios.restype = None

# SetDBInventarios(DBHandle: Integer): Integer; stdcall;
microsip_dll.SetDBInventarios.argtypes = [c_int]
microsip_dll.SetDBInventarios.restype = c_int