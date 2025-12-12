from django.db.models import *
from django.db import transaction
from django.contrib.auth.models import User, Group
from django.shortcuts import get_object_or_404
from rest_framework import permissions, generics, status
from rest_framework.response import Response
from datetime import date, datetime

# Importaciones locales
from ..models import Empleado
from ..serializers import EmpleadoSerializer, UserSerializer

def calcular_edad(fecha_nacimiento_str):
    """
    Calcula la edad basada en una fecha de nacimiento en string (YYYY-MM-DD) o objeto date.
    Retorna la edad como entero o None si hay error.
    """
    if not fecha_nacimiento_str:
        return None
    
    try:
        # Si ya viene como objeto date/datetime
        if isinstance(fecha_nacimiento_str, (date, datetime)):
            nacimiento = fecha_nacimiento_str
        else:
            # Parsear string YYYY-MM-DD
            nacimiento = datetime.strptime(fecha_nacimiento_str, "%Y-%m-%d").date()
            
        today = date.today()
        # Calculo de edad: resta años y ajusta si aún no ha pasado el cumpleaños este año
        edad = today.year - nacimiento.year - ((today.month, today.day) < (nacimiento.month, nacimiento.day))
        return edad
    except ValueError:
        return None

class AdminAll(generics.CreateAPIView):
    """
    Vista para listar todos los administradores.
    """
    permission_classes = (permissions.IsAuthenticated,)
    
    def get(self, request, *args, **kwargs):
        admins = Empleado.objects.filter(puesto='ADMIN', user__is_active=True).order_by("id")
        lista = EmpleadoSerializer(admins, many=True).data
        return Response(lista, 200)

class AdminView(generics.CreateAPIView):
    """
    Vista para gestión individual de administrador (CRUD).
    """
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.AllowAny()]
        return [permissions.IsAuthenticated()]
    
    def get(self, request, *args, **kwargs):
        admin_id = request.GET.get("id")
        if not admin_id:
            return Response({"error": "ID es requerido"}, status=400)
            
        admin = get_object_or_404(Empleado, id=admin_id, puesto='ADMIN')
        admin_data = EmpleadoSerializer(admin, many=False).data
        return Response(admin_data, 200)
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """Crear nuevo administrador con cálculo automático de edad"""
        data = request.data.copy()
        
        if 'email' in data and 'username' not in data:
            data['username'] = data['email']

        user_serializer = UserSerializer(data=data)
        
        if user_serializer.is_valid():
            role = data.get('rol', 'ADMIN')
            
            # --- LÓGICA DE EDAD AUTOMÁTICA ---
            fecha_nac = data.get("fecha_nacimiento")
            edad_calculada = calcular_edad(fecha_nac)
            
            # Opcional: Validar si la edad es legal (ej. > 18)
            if edad_calculada is not None and edad_calculada < 18:
                return Response({"error": "El administrador debe ser mayor de edad"}, 400)
            # ---------------------------------

            if User.objects.filter(email=data.get('email')).exists():
                return Response({"message": f"El email {data.get('email')} ya está registrado"}, 400)

            # Crear Usuario
            user = User.objects.create(
                username=data['email'],
                email=data['email'],
                first_name=data.get('first_name'),
                last_name=data.get('last_name'),
                is_active=True
            )
            
            user.set_password(data.get('password'))
            user.save()

            group, created = Group.objects.get_or_create(name=role)
            group.user_set.add(user)

            clave_interna = data.get("clave_interna") or data.get("clave_admin")
            
            empleado = Empleado.objects.create(
                user=user,
                clave_interna=clave_interna,
                telefono=data.get("telefono"),
                rfc=data.get("rfc"),
                fecha_nacimiento=fecha_nac,
                edad=edad_calculada, # Se guarda el valor calculado
                puesto='ADMIN'
            )
            
            return Response({"admin_created_id": empleado.id}, 201)

        return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        """Actualizar administrador existente recalculando edad si cambia fecha"""
        admin_id = request.data.get("id")
        if not admin_id:
             return Response({"error": "ID es requerido para actualizar"}, status=400)

        empleado = get_object_or_404(Empleado, id=admin_id, puesto='ADMIN')
        
        # --- ACTUALIZACIÓN Y RECÁLCULO DE EDAD ---
        nueva_fecha = request.data.get("fecha_nacimiento")
        if nueva_fecha:
            empleado.fecha_nacimiento = nueva_fecha
            # Si cambia la fecha, recalculamos la edad
            nueva_edad = calcular_edad(nueva_fecha)
            if nueva_edad:
                empleado.edad = nueva_edad
        
        nueva_clave = request.data.get("clave_interna") or request.data.get("clave_admin")
        if nueva_clave:
            empleado.clave_interna = nueva_clave
            
        empleado.telefono = request.data.get("telefono", empleado.telefono)
        empleado.rfc = request.data.get("rfc", empleado.rfc)
        
        # Guardamos cambios del empleado
        empleado.save()
        
        # Actualizamos usuario
        user = empleado.user
        user.first_name = request.data.get("first_name", user.first_name)
        user.last_name = request.data.get("last_name", user.last_name)
        user.save()
        
        return Response({
            "message": "Administrador actualizado correctamente", 
            "admin": EmpleadoSerializer(empleado).data
        }, 200)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        """Eliminar administrador (Baja lógica)"""
        admin_id = request.GET.get("id")
        if not admin_id:
            return Response({"error": "ID es requerido"}, status=400)
            
        empleado = get_object_or_404(Empleado, id=admin_id, puesto='ADMIN')
        user = empleado.user
        user.is_active = False
        user.save()
        
        return Response({"message": "Administrador eliminado correctamente"}, 200)