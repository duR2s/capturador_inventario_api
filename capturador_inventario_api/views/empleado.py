from django.db.models import Q
from django.db import transaction
from django.contrib.auth.models import User, Group
from django.shortcuts import get_object_or_404
from rest_framework import permissions, generics, status
from rest_framework.views import APIView
from rest_framework.response import Response
from datetime import date, datetime

# Importaciones locales
from ..models import Empleado
from ..serializers import EmpleadoSerializer, UserSerializer

def calcular_edad(fecha_nacimiento_str):
    if not fecha_nacimiento_str:
        return None
    try:
        if isinstance(fecha_nacimiento_str, (date, datetime)):
            nacimiento = fecha_nacimiento_str
        else:
            nacimiento = datetime.strptime(fecha_nacimiento_str, "%Y-%m-%d").date()
        today = date.today()
        edad = today.year - nacimiento.year - ((today.month, today.day) < (nacimiento.month, nacimiento.day))
        return edad
    except ValueError:
        return None

# --- VISTA 1: SOLO LISTADO ---
class UsuarioListView(APIView):
    """
    Endpoint: /api/lista-usuarios/
    Propósito: Obtener el listado de usuarios con filtros opcionales.
    """
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request, *args, **kwargs):
        rol_filtro = request.query_params.get("rol") # Ej: 'ADMIN', 'CAPTURADOR'
        busqueda = request.query_params.get("q") # Búsqueda por nombre/clave

        queryset = Empleado.objects.filter(user__is_active=True).order_by("id")

        if rol_filtro:
            queryset = queryset.filter(puesto=rol_filtro)
        
        if busqueda:
            queryset = queryset.filter(
                Q(user__first_name__icontains=busqueda) | 
                Q(user__last_name__icontains=busqueda) |
                Q(user__email__icontains=busqueda) |
                Q(clave_interna__icontains=busqueda)
            )

        data = EmpleadoSerializer(queryset, many=True).data
        return Response(data, status=200)


# --- VISTA 2: GESTIÓN INDIVIDUAL (CRUD) ---
class UsuarioGestionView(APIView):
    """
    Endpoint: /api/usuarios/
    Propósito: Crear, Leer uno, Editar y Eliminar un usuario específico.
    """
    permission_classes = [permissions.IsAuthenticated]

    # GET UN USUARIO
    def get(self, request, *args, **kwargs):
        usuario_id = request.query_params.get("id")
        if not usuario_id:
            return Response({"error": "Se requiere el ID del usuario para esta consulta."}, status=400)

        empleado = get_object_or_404(Empleado, id=usuario_id)
        return Response(EmpleadoSerializer(empleado).data, status=200)

    # CREAR USUARIO (POST)
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        data = request.data.copy()
        
        if 'email' in data and 'username' not in data:
            data['username'] = data['email']
        
        puesto = data.get('puesto', 'CAPTURADOR')
        if puesto not in ['ADMIN', 'CAPTURADOR', 'OTRO']:
            return Response({"error": f"El puesto '{puesto}' no es válido."}, status=400)

        fecha_nac = data.get("fecha_nacimiento")
        edad = calcular_edad(fecha_nac)
        
        if puesto == 'ADMIN' and (edad is None or edad < 18):
            return Response({"error": "Un Administrador debe ser mayor de edad obligatoriamente."}, status=400)

        if User.objects.filter(email=data.get('email')).exists():
            return Response({"error": f"El email {data.get('email')} ya existe."}, status=400)

        user_serializer = UserSerializer(data=data)
        if user_serializer.is_valid():
            user = User.objects.create(
                username=data['email'],
                email=data['email'],
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                is_active=True
            )
            user.set_password(data.get('password'))
            user.save()

            group, _ = Group.objects.get_or_create(name=puesto)
            group.user_set.add(user)

            clave = data.get("clave_interna") or data.get("clave_admin")

            empleado = Empleado.objects.create(
                user=user,
                clave_interna=clave,
                telefono=data.get("telefono"),
                rfc=data.get("rfc"),
                fecha_nacimiento=fecha_nac,
                edad=edad,
                puesto=puesto
            )
            
            return Response({
                "mensaje": f"{puesto} creado exitosamente",
                "id": empleado.id
            }, status=201)
        
        return Response(user_serializer.errors, status=400)

    # ACTUALIZAR USUARIO (PUT)
    @transaction.atomic
    def put(self, request, *args, **kwargs):
        usuario_id = request.data.get("id")
        if not usuario_id:
            return Response({"error": "ID es requerido"}, status=400)

        empleado = get_object_or_404(Empleado, id=usuario_id)
        data = request.data

        if "fecha_nacimiento" in data:
            empleado.fecha_nacimiento = data["fecha_nacimiento"]
            empleado.edad = calcular_edad(data["fecha_nacimiento"])
        
        clave = data.get("clave_interna") or data.get("clave_admin")
        if clave:
            empleado.clave_interna = clave

        empleado.telefono = data.get("telefono", empleado.telefono)
        empleado.rfc = data.get("rfc", empleado.rfc)

        nuevo_puesto = data.get("puesto")
        if nuevo_puesto and nuevo_puesto != empleado.puesto:
            if nuevo_puesto not in ['ADMIN', 'CAPTURADOR', 'OTRO']:
                 return Response({"error": "Puesto inválido"}, status=400)
            
            antiguo_grupo = Group.objects.filter(name=empleado.puesto).first()
            if antiguo_grupo: antiguo_grupo.user_set.remove(empleado.user)
            
            nuevo_grupo, _ = Group.objects.get_or_create(name=nuevo_puesto)
            nuevo_grupo.user_set.add(empleado.user)
            
            empleado.puesto = nuevo_puesto

        empleado.save()

        user = empleado.user
        user.first_name = data.get("first_name", user.first_name)
        user.last_name = data.get("last_name", user.last_name)
        user.save()

        return Response({"mensaje": "Actualizado correctamente"}, status=200)

    # ELIMINAR USUARIO (DELETE)
    def delete(self, request, *args, **kwargs):
        usuario_id = request.query_params.get("id")
        if not usuario_id:
             usuario_id = request.data.get("id")

        if not usuario_id:
            return Response({"error": "ID requerido"}, status=400)

        empleado = get_object_or_404(Empleado, id=usuario_id)
        empleado.user.is_active = False
        empleado.user.save()

        return Response({"mensaje": "Usuario desactivado correctamente"}, status=200)