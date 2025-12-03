from django.db.models import *
from django.db import transaction
# IMPORTANTE: Cambiamos las importaciones viejas
from capturador_inventario_api.models import Empleado
from capturador_inventario_api.serializers import EmpleadoSerializer, UserSerializer
from capturador_inventario_api.models import *
from rest_framework import permissions
from rest_framework import generics
from rest_framework import status
from rest_framework.response import Response
from django.contrib.auth.models import Group
from django.shortcuts import get_object_or_404


class AdminAll(generics.CreateAPIView):
    # Esta función es esencial para todo donde se requiera autorización de inicio de sesión (token)
    permission_classes = (permissions.IsAuthenticated,)
    
    # Invocamos la petición GET para obtener todos los administradores (Empleados con puesto ADMIN)
    def get(self, request, *args, **kwargs):
        # Filtramos solo los que son ADMIN
        admins = Empleado.objects.filter(puesto='ADMIN', user__is_active=1).order_by("id")
        lista = EmpleadoSerializer(admins, many=True).data
        return Response(lista, 200)

class AdminView(generics.CreateAPIView):
    # Obtener usuario por ID
    permission_classes = (permissions.IsAuthenticated,)
    
    def get(self, request, *args, **kwargs):
        admin = get_object_or_404(Empleado, id=request.GET.get("id"), puesto='ADMIN')
        admin_data = EmpleadoSerializer(admin, many=False).data
        return Response(admin_data, 200)
    
    # Registrar nuevo administrador
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        user_serializer = UserSerializer(data=request.data)
        
        if user_serializer.is_valid():
            role = request.data.get('rol', 'ADMIN') # Default a admin si no viene
            first_name = request.data['first_name']
            last_name = request.data['last_name']
            email = request.data['email']
            password = request.data['password']

            existing_user = User.objects.filter(email=email).first()

            if existing_user:
                return Response({"message": "Username "+email+", is already taken"}, 400)

            user = User.objects.create(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=1
            )
            
            user.set_password(password)
            user.save()

            # Asignar grupo de Django
            group, created = Group.objects.get_or_create(name=role)
            group.user_set.add(user)
            user.save()

            # Crear el perfil de Empleado
            # Mapeamos los campos viejos a los nuevos unificados
            empleado = Empleado.objects.create(
                user=user,
                clave_interna=request.data.get("clave_admin"), # Ahora va a clave_interna
                telefono=request.data.get("telefono"),
                fecha_nacimiento=request.data.get("fecha_nacimiento"),
                edad=request.data.get("edad"),
                puesto='ADMIN' # Forzamos el puesto de Administrador
                # ocupacion ya no existe en el modelo nuevo, se ignora
            )
            empleado.save()

            return Response({"admin_created_id": empleado.id}, 201)

        return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    # Actualizar datos del administrador
    @transaction.atomic
    def put(self, request, *args, **kwargs):
        permission_classes = (permissions.IsAuthenticated,)
        
        # Obtenemos el empleado
        empleado = get_object_or_404(Empleado, id=request.data["id"])
        
        # Actualizamos campos del Empleado
        empleado.clave_interna = request.data.get("clave_admin", empleado.clave_interna)
        empleado.telefono = request.data.get("telefono", empleado.telefono)
        empleado.fecha_nacimiento = request.data.get("fecha_nacimiento", empleado.fecha_nacimiento)
        empleado.edad = request.data.get("edad", empleado.edad)
        empleado.save()
        
        # Actualizamos datos del usuario asociado
        user = empleado.user
        user.first_name = request.data.get("first_name", user.first_name)
        user.last_name = request.data.get("last_name", user.last_name)
        user.save()
        
        return Response({
            "message": "Administrador actualizado correctamente", 
            "admin": EmpleadoSerializer(empleado).data
        }, 200)