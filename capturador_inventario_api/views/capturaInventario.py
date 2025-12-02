from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from ..serializers import CapturaSerializer

class CapturaInventarioView(APIView):
    """
    Endpoint para recibir capturas de inventario.
    Soporta modo offline y garantiza atomicidad (todo o nada).
    """
    
    def post(self, request, *args, **kwargs):
        """
        Recibe:
        {
            "folio": "INV-2023-001",
            "capturador": 1,
            "estado": "PROGRESO",
            "modo_offline": true,             <-- Opcional
            "fecha_reportada": "2023-10-27T10:00:00Z", <-- Requerido si modo_offline=true
            "detalles": [
                {"producto_codigo": "750123456", "cantidad_contada": 10},
                {"producto_codigo": "A001", "cantidad_contada": 5}
            ]
        }
        """
        serializer = CapturaSerializer(data=request.data)
        
        if serializer.is_valid():
            try:
                # El bloque atomic asegura que si algo falla al guardar (BD, red interna), 
                # se hace rollback de todo (cabecera y detalles).
                with transaction.atomic():
                    captura = serializer.save()
                    
                return Response({
                    "mensaje": "Captura guardada exitosamente.",
                    "folio": captura.folio,
                    "id": captura.id,
                    "fecha_registrada": captura.fecha_captura
                }, status=status.HTTP_201_CREATED)
                
            except Exception as e:
                # Error inesperado a nivel de base de datos o lógica interna
                return Response({
                    "error": "Error interno al procesar la captura.",
                    "detalle": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        # Si la validación falla (ej. códigos incorrectos), devolvemos el error detallado
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)