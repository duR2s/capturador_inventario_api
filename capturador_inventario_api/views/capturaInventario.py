from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from django.db import transaction
from django.shortcuts import get_object_or_404
# Importamos InventarioArticulo
from ..models import Captura, DetalleCaptura, Almacen, Articulo, ClaveAuxiliar, TicketSalida, InventarioArticulo
from ..serializers import CapturaSerializer, DetalleCapturaSerializer, AlmacenSerializer, TicketSalidaSerializer

class AlmacenOptionsView(APIView):
    def get(self, request, *args, **kwargs):
        try:
            almacenes = Almacen.objects.filter(activo_web=True).order_by('nombre')
            serializer = AlmacenSerializer(almacenes, many=True)
            return Response(serializer.data, status=status.HTTP_200_OK)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

class ArticuloBusquedaView(APIView):
    """
    Endpoint: GET /api/inventario/buscar-articulo/?codigo=XYZ&almacen=ID
    Retorna datos del artículo incluyendo existencia en el almacén solicitado.
    """
    def get(self, request, *args, **kwargs):
        codigo = request.query_params.get('codigo', '').strip()
        almacen_id = request.query_params.get('almacen', None)

        if not codigo:
            return Response({"error": "Código no proporcionado"}, status=status.HTTP_400_BAD_REQUEST)

        # 1. Buscar Artículo
        articulo = Articulo.objects.filter(clave__iexact=codigo).first()
        if not articulo:
            aux = ClaveAuxiliar.objects.filter(clave__iexact=codigo).select_related('articulo').first()
            if aux:
                articulo = aux.articulo
        
        if articulo:
            existencia = 0
            # 2. Si hay almacén, buscar existencia
            if almacen_id:
                inv = InventarioArticulo.objects.filter(articulo=articulo, almacen_id=almacen_id).first()
                if inv:
                    existencia = inv.existencia

            data = {
                "id": articulo.id,
                "clave": articulo.clave,
                "nombre": articulo.nombre,
                "existencia_teorica": existencia # <-- Enviamos el dato
            }
            return Response(data, status=status.HTTP_200_OK)
        else:
            return Response({"error": "Producto no encontrado"}, status=status.HTTP_404_NOT_FOUND)

class CapturaInventarioView(APIView):
    def get(self, request, *args, **kwargs):
        capturas = Captura.objects.filter(capturador=request.user).order_by('-fecha_captura')
        serializer = CapturaSerializer(capturas, many=True)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def post(self, request, *args, **kwargs):
        serializer = CapturaSerializer(data=request.data)
        if serializer.is_valid():
            try:
                with transaction.atomic():
                    captura = serializer.save()
                return Response({
                    "mensaje": "Captura guardada exitosamente.",
                    "folio": captura.folio,
                    "id": captura.id,
                    "fecha_registrada": captura.fecha_captura
                }, status=status.HTTP_201_CREATED)
            except Exception as e:
                return Response({
                    "error": "Error interno al procesar la captura.",
                    "detalle": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class CapturaDetailView(APIView):
    def get(self, request, pk, *args, **kwargs):
        captura = get_object_or_404(Captura, pk=pk)
        serializer = CapturaSerializer(captura)
        return Response(serializer.data, status=status.HTTP_200_OK)

    def delete(self, request, pk, *args, **kwargs):
        captura = get_object_or_404(Captura, pk=pk)
        try:
            captura.delete()
            return Response({"mensaje": "Captura eliminada correctamente"}, status=status.HTTP_204_NO_CONTENT)
        except Exception as e:
            return Response({"error": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

    def patch(self, request, pk, *args, **kwargs):
        captura = get_object_or_404(Captura, pk=pk)
        serializer = CapturaSerializer(captura, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_200_OK)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class SincronizarCapturaView(APIView):
    def post(self, request, pk, *args, **kwargs):
        captura = get_object_or_404(Captura, pk=pk)

        if not isinstance(request.data, list):
            return Response(
                {"error": "Se esperaba una lista (array) de detalles."}, 
                status=status.HTTP_400_BAD_REQUEST
            )

        serializer = DetalleCapturaSerializer(data=request.data, many=True)

        if serializer.is_valid():
            try:
                with transaction.atomic():
                    serializer.save(captura=captura)
                
                todos_los_detalles = DetalleCaptura.objects.filter(captura=captura).order_by('-id')
                respuesta_serializer = DetalleCapturaSerializer(todos_los_detalles, many=True)
                
                return Response(respuesta_serializer.data, status=status.HTTP_200_OK)

            except Exception as e:
                return Response({
                    "error": "Error durante la sincronización masiva.",
                    "detalle": str(e)
                }, status=status.HTTP_500_INTERNAL_SERVER_ERROR)
        
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)


class DetalleIndividualView(APIView):
    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        if 'captura_id' in data:
            data['captura'] = data.pop('captura_id')

        serializer = DetalleCapturaSerializer(data=data)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data, status=status.HTTP_201_CREATED)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
    
    def delete(self, request, pk, *args, **kwargs):
        detalle = get_object_or_404(DetalleCaptura, pk=pk)
        detalle.delete()
        return Response(status=status.HTTP_204_NO_CONTENT)

    def patch(self, request, pk, *args, **kwargs):
        detalle = get_object_or_404(DetalleCaptura, pk=pk)
        serializer = DetalleCapturaSerializer(detalle, data=request.data, partial=True)
        if serializer.is_valid():
            serializer.save()
            return Response(serializer.data)
        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

class TicketCreateView(APIView):
    def post(self, request, *args, **kwargs):
        serializer = TicketSalidaSerializer(data=request.data)
        
        if serializer.is_valid():
            detalle_id = request.data.get('detalle')
            cantidad_ticket = serializer.validated_data.get('cantidad')
            
            detalle = get_object_or_404(DetalleCaptura, pk=detalle_id)
            
            try:
                with transaction.atomic():
                    if cantidad_ticket > detalle.cantidad_contada:
                        return Response({
                            "error": f"No se pueden retirar {cantidad_ticket} piezas. Solo hay {detalle.cantidad_contada} capturadas."
                        }, status=status.HTTP_400_BAD_REQUEST)

                    detalle.cantidad_contada -= cantidad_ticket
                    detalle.save()

                    ticket = serializer.save()

                return Response({
                    "mensaje": "Ticket generado y cantidad descontada.",
                    "ticket_id": ticket.id,
                    "nueva_cantidad_detalle": detalle.cantidad_contada
                }, status=status.HTTP_201_CREATED)

            except Exception as e:
                return Response({"error": "Error al procesar ticket", "detalle": str(e)}, status=status.HTTP_500_INTERNAL_SERVER_ERROR)

        return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)