from django.db.models import *
from django.db import transaction
from capturador_inventario_api.models import Empleado
from capturador_inventario_api.serializers import EmpleadoSerializer, UserSerializer
from rest_framework import permissions
from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
from django.contrib.auth.models import Group, User
from django.shortcuts import get_object_or_404

class CapturadorAll(generics.CreateAPIView):
    # Requiere token para ver la lista
    permission_classes = (permissions.IsAuthenticated,)
    
    def get(self, request, *args, **kwargs):
        # Filtramos SOLO los empleados que son CAPTURADOR y que tienen usuario activo
        capturadores = Empleado.objects.filter(puesto='CAPTURADOR', user__is_active=1).order_by("id")
        lista = EmpleadoSerializer(capturadores, many=True).data
        return Response(lista, 200)

class CapturadorView(generics.CreateAPIView):
    # Requiere token
    permission_classes = (permissions.IsAuthenticated,)

    # Obtener un capturador específico por ID
    def get(self, request, *args, **kwargs):
        # Buscamos por ID pero asegurando que sea un CAPTURADOR
        capturador = get_object_or_404(Empleado, id=request.GET.get("id"), puesto='CAPTURADOR')
        data = EmpleadoSerializer(capturador, many=False).data
        return Response(data, 200)
    
    # Registrar nuevo capturador
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        user_serializer = UserSerializer(data=request.data)
        
        if user_serializer.is_valid():
            # Datos específicos
            role = 'CAPTURADOR' # Forzamos el rol
            first_name = request.data['first_name']
            last_name = request.data['last_name']
            email = request.data['email']
            password = request.data['password']

            # Validar unicidad del email
            if User.objects.filter(email=email).exists():
                return Response({"message": f"El usuario {email} ya existe"}, 400)

            # 1. Crear Usuario Django
            user = User.objects.create(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=1
            )
            user.set_password(password)
            user.save()

            # 2. Asignar Grupo
            group, created = Group.objects.get_or_create(name=role)
            group.user_set.add(user)
            user.save()

            # 3. Crear Empleado (Perfil)
            # Nota: Mapeamos 'id_trabajador' (frontend) a 'clave_interna' (bd)
            empleado = Empleado.objects.create(
                user=user,
                clave_interna=request.data.get("id_trabajador"), 
                telefono=request.data.get("telefono"),
                edad=request.data.get("edad"),
                # Fecha nacimiento es opcional para capturadores, pero si viene la guardamos
                fecha_nacimiento=request.data.get("fecha_nacimiento"), 
                puesto='CAPTURADOR'
            )
            empleado.save()

            return Response({"capturador_created_id": empleado.id}, 201)

        return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Actualizar datos del capturador
    @transaction.atomic
    def put(self, request, *args, **kwargs):
        permission_classes = (permissions.IsAuthenticated,)
        
        # Validamos que el ID corresponda a un capturador
        capturador = get_object_or_404(Empleado, id=request.data["id"], puesto='CAPTURADOR')
        
        # Actualizamos datos del perfil
        # Usamos .get() para permitir actualizaciones parciales si el frontend no envía todo
        capturador.clave_interna = request.data.get("id_trabajador", capturador.clave_interna)
        capturador.telefono = request.data.get("telefono", capturador.telefono)
        capturador.edad = request.data.get("edad", capturador.edad)
        if "fecha_nacimiento" in request.data:
            capturador.fecha_nacimiento = request.data["fecha_nacimiento"]
            
        capturador.save()
        
        # Actualizamos datos del usuario
        user = capturador.user
        user.first_name = request.data.get("first_name", user.first_name)
        user.last_name = request.data.get("last_name", user.last_name)
        user.save()
        
        return Response({
            "message": "Capturador actualizado correctamente", 
            "capturador": EmpleadoSerializer(capturador).data
        }, 200)