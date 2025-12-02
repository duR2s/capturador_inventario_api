import time
from django.utils import timezone
from capturador_inventario_api.microsip_api.microsip_api_sync_Articulos import InventariosService

def task_sincronizar_inventario():
    """
    Tarea envoltorio compatible con Django-Q para ejecutar la sincronización.
    Esta función es la que debes llamar desde el Schedule de Django-Q.
    """
    print(f"[{timezone.now()}] Iniciando tarea en segundo plano: Sincronización Microsip...")
    
    # Instanciamos el servicio. 
    # Nota: La conexión se maneja internamente en el método sincronizar_articulos gracias al decorador.
    service = InventariosService()
    
    try:
        # Ejecutamos la lógica de sincronización
        resultado = service.sincronizar_articulos()
        
        mensaje = (
            f"Tarea finalizada con éxito. "
            f"Creados: {resultado.get('articulos_creados')}, "
            f"Actualizados: {resultado.get('articulos_actualizados')}, "
            f"Desactivados: {resultado.get('articulos_desactivados')}."
        )
        print(f"[{timezone.now()}] {mensaje}")
        return mensaje

    except Exception as e:
        error_msg = f"Error crítico en tarea de sincronización: {str(e)}"
        print(f"[{timezone.now()}] {error_msg}")
        # Relanzamos la excepción para que Django-Q marque la tarea como 'Failed'
        raise e