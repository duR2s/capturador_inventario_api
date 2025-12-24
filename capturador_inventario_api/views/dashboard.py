from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework.permissions import IsAuthenticated
from rest_framework import status
from django.db.models import Count, Q, F, Case, When, IntegerField
from django.utils import timezone
from datetime import timedelta
import calendar

# Importamos los modelos necesarios desde el directorio padre
from ..models import Captura, Articulo, DetalleCaptura

# --- Intentamos importar Schedule de Django-Q ---
try:
    from django_q.models import Schedule
except ImportError:
    Schedule = None

class DashboardKPIView(APIView):
    """
    Endpoint: /api/dashboard/kpi/
    Retorna indicadores clave del mes actual y la próxima sincronización.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        # Primer día del mes actual
        start_of_month = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        
        # 1. Artículos diferentes capturados en este mes (LÓGICA MODIFICADA)
        # En lugar de ver sincronización, vemos cuántos artículos distintos se han contado en capturas del mes.
        articulos_count = DetalleCaptura.objects.filter(
            captura__fecha_captura__gte=start_of_month
        ).values('articulo').distinct().count()

        # 2. Capturas realizadas este mes
        capturas_qs = Captura.objects.filter(
            fecha_captura__gte=start_of_month
        )
        capturas_count = capturas_qs.count()

        # 3. Capturador con más capturas este mes
        top_capturador_data = capturas_qs.exclude(capturador__isnull=True).values(
            'capturador__username', 
            'capturador__first_name', 
            'capturador__last_name'
        ).annotate(
            total=Count('id')
        ).order_by('-total').first()

        top_capturador = None
        if top_capturador_data:
            f_name = top_capturador_data.get('capturador__first_name', '') or ''
            l_name = top_capturador_data.get('capturador__last_name', '') or ''
            nombre = f"{f_name} {l_name}".strip()
            
            if not nombre:
                nombre = top_capturador_data.get('capturador__username', 'Usuario')
            
            top_capturador = {
                "nombre": nombre,
                "total": top_capturador_data['total']
            }

        # 4. Próxima Sincronización
        proxima_sincronizacion = None
        if Schedule:
            tarea_programada = Schedule.objects.filter(
                func__icontains='task_sincronizar_inventario'
            ).order_by('next_run').first()

            if tarea_programada:
                proxima_sincronizacion = tarea_programada.next_run

        return Response({
            "articulos_actualizados_mes": articulos_count,
            "capturas_mes": capturas_count,
            "top_capturador_mes": top_capturador,
            "proxima_sincronizacion": proxima_sincronizacion
        }, status=status.HTTP_200_OK)


class DashboardChartsView(APIView):
    """
    Endpoint: /api/dashboard/charts/
    Retorna datos históricos agrupados por mes (últimos 5 meses).
    PROCESAMIENTO EN MEMORIA (PYTHON) PARA EVITAR ERRORES DE TIMEZONE EN BD.
    """
    permission_classes = [IsAuthenticated]

    def get(self, request, *args, **kwargs):
        now = timezone.now()
        start_date = now - timedelta(days=150) 

        # --- ESTRATEGIA SEGURA: TRAER DATOS CRUDOS Y AGRUPAR EN PYTHON ---
        
        # 1. Obtener todas las capturas relevantes con sus campos necesarios
        capturas_raw = Captura.objects.filter(
            fecha_captura__gte=start_date
        ).values('id', 'fecha_captura')

        # 2. Obtener detalles relevantes, optimizando la query
        detalles_raw = DetalleCaptura.objects.filter(
            captura__fecha_captura__gte=start_date
        ).values(
            'captura__fecha_captura', 
            'cantidad_contada', 
            'existencia_sistema_al_momento'
        )

        data_map = {}

        # Helper para inicializar mes en el mapa
        def init_month(mes_key, nombre_mes):
            if mes_key not in data_map:
                data_map[mes_key] = {
                    "fecha": mes_key,
                    "nombre_mes": nombre_mes,
                    "capturas_totales": 0,
                    "articulos_con_diferencia": 0,
                    "articulos_exactos": 0
                }

        # --- A. PROCESAR CAPTURAS (Conteo total) ---
        for c in capturas_raw:
            fecha = c['fecha_captura']
            if fecha:
                # Convertir a zona horaria local si es necesario, o usar UTC directo
                # Aquí usamos la fecha tal cual viene del objeto datetime de Python
                mes_key = f"{fecha.year}-{str(fecha.month).zfill(2)}"
                try:
                    nombre_mes = calendar.month_name[fecha.month]
                except (IndexError, ValueError):
                    nombre_mes = "Desconocido"
                
                init_month(mes_key, nombre_mes)
                data_map[mes_key]["capturas_totales"] += 1

        # --- B. PROCESAR DETALLES (Diferencias vs Exactos) ---
        for d in detalles_raw:
            fecha = d['captura__fecha_captura']
            cant_contada = d['cantidad_contada']
            cant_sistema = d['existencia_sistema_al_momento']

            if fecha:
                mes_key = f"{fecha.year}-{str(fecha.month).zfill(2)}"
                try:
                    nombre_mes = calendar.month_name[fecha.month]
                except (IndexError, ValueError):
                    nombre_mes = "Desconocido"
                
                init_month(mes_key, nombre_mes)

                # Lógica de comparación exacta (Decimal vs Decimal)
                if cant_contada == cant_sistema:
                    data_map[mes_key]["articulos_exactos"] += 1
                else:
                    data_map[mes_key]["articulos_con_diferencia"] += 1

        # Ordenar cronológicamente
        final_data = sorted(data_map.values(), key=lambda x: x['fecha'])

        return Response(final_data, status=status.HTTP_200_OK)