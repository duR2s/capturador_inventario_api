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

class EmpleadoAll(generics.CreateAPIView):
    """
    Vista para listar TODOS los empleados (Excluyendo Administradores).
    """
    permission_classes = (permissions.IsAuthenticated,)
    
    def get(self, request, *args, **kwargs):
        # Filtramos a todos los usuarios activos que NO sean ADMIN
        empleados = Empleado.objects.exclude(puesto='ADMIN').filter(user__is_active=True).order_by("id")
        lista = EmpleadoSerializer(empleados, many=True).data
        return Response(lista, 200)

class EmpleadoView(generics.CreateAPIView):
    """
    Vista para gestión individual de Empleado Genérico (CRUD).
    Maneja cualquier puesto que no sea ADMIN (ej. CAPTURADOR, OTRO, ALMACENISTA).
    """
    
    def get_permissions(self):
        if self.request.method == 'POST':
            # Puedes cambiar esto a IsAuthenticated si solo admins pueden registrar empleados
            return [permissions.AllowAny()] 
        return [permissions.IsAuthenticated()]
    
    def get(self, request, *args, **kwargs):
        """Obtener un empleado por ID"""
        empleado_id = request.GET.get("id")
        if not empleado_id:
            return Response({"error": "ID es requerido"}, status=400)
            
        # Buscamos cualquier empleado que no sea ADMIN
        empleado = get_object_or_404(Empleado.objects.exclude(puesto='ADMIN'), id=empleado_id)
        
        data = EmpleadoSerializer(empleado, many=False).data
        return Response(data, 200)
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """Crear nuevo empleado con cálculo automático de edad"""
        data = request.data.copy()
        
        if 'email' in data and 'username' not in data:
            data['username'] = data['email']

        user_serializer = UserSerializer(data=data)
        
        if user_serializer.is_valid():
            # Obtenemos el puesto del request, por defecto CAPTURADOR
            puesto = data.get('puesto', 'CAPTURADOR')
            
            # Validación de seguridad: No permitir crear ADMINs desde esta vista
            if puesto == 'ADMIN':
                return Response(
                    {"error": "Esta vista no permite crear Administradores. Use /api/admin/"}, 
                    status=403
                )
            
            # --- LÓGICA DE EDAD AUTOMÁTICA ---
            fecha_nac = data.get("fecha_nacimiento")
            edad_calculada = calcular_edad(fecha_nac)
            
            # Opcional: Validar si la edad es legal para empleados (ej. > 18)
            # if edad_calculada is not None and edad_calculada < 18:
            #     return Response({"error": "El empleado debe ser mayor de edad"}, 400)
            
            first_name = data.get('first_name')
            last_name = data.get('last_name')
            email = data.get('email')
            password = data.get('password')

            if User.objects.filter(email=email).exists():
                return Response({"message": f"El email {email} ya está registrado"}, 400)

            # 1. Crear Usuario Django
            user = User.objects.create(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            
            user.set_password(password)
            user.save()

            # 2. Asignar grupo basado en el puesto (rol)
            group, created = Group.objects.get_or_create(name=puesto)
            group.user_set.add(user)

            # 3. Crear Perfil Empleado
            clave_interna = data.get("clave_interna")
            
            empleado = Empleado.objects.create(
                user=user,
                clave_interna=clave_interna,
                telefono=data.get("telefono"),
                rfc=data.get("rfc"),
                fecha_nacimiento=fecha_nac,
                edad=edad_calculada, # Guardamos edad calculada
                puesto=puesto
            )
            
            return Response({"empleado_created_id": empleado.id}, 201)

        return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        """Actualizar empleado existente"""
        empleado_id = request.data.get("id")
        if not empleado_id:
             return Response({"error": "ID es requerido para actualizar"}, status=400)

        # Buscamos empleado no-admin
        empleado = get_object_or_404(Empleado.objects.exclude(puesto='ADMIN'), id=empleado_id)
        
        # Actualizamos puesto si se envía, validando que no intenten escalar a ADMIN
        nuevo_puesto = request.data.get("puesto")
        if nuevo_puesto:
            if nuevo_puesto == 'ADMIN':
                return Response({"error": "No se puede promover a ADMIN desde esta vista"}, 403)
            
            # Si cambia el puesto, actualizamos también el grupo de Django
            if empleado.puesto != nuevo_puesto:
                antiguo_grupo = Group.objects.filter(name=empleado.puesto).first()
                if antiguo_grupo:
                    antiguo_grupo.user_set.remove(empleado.user)
                
                nuevo_grupo, _ = Group.objects.get_or_create(name=nuevo_puesto)
                nuevo_grupo.user_set.add(empleado.user)
                
                empleado.puesto = nuevo_puesto

        # --- ACTUALIZACIÓN Y RECÁLCULO DE EDAD ---
        nueva_fecha = request.data.get("fecha_nacimiento")
        if nueva_fecha:
            empleado.fecha_nacimiento = nueva_fecha
            # Si cambia la fecha, recalculamos la edad
            nueva_edad = calcular_edad(nueva_fecha)
            if nueva_edad is not None:
                empleado.edad = nueva_edad

        # Actualizamos datos del Empleado
        if request.data.get("clave_interna"):
            empleado.clave_interna = request.data.get("clave_interna")
            
        empleado.telefono = request.data.get("telefono", empleado.telefono)
        empleado.rfc = request.data.get("rfc", empleado.rfc)
        
        # Guardamos cambios del empleado
        empleado.save()
        
        # Actualizamos datos del usuario asociado (User)
        user = empleado.user
        user.first_name = request.data.get("first_name", user.first_name)
        user.last_name = request.data.get("last_name", user.last_name)
        user.save()
        
        return Response({
            "message": "Empleado actualizado correctamente", 
            "empleado": EmpleadoSerializer(empleado).data
        }, 200)

    @transaction.atomic
    def delete(self, request, *args, **kwargs):
        """Eliminar empleado (Baja lógica)"""
        empleado_id = request.GET.get("id")
        if not empleado_id:
            return Response({"error": "ID es requerido"}, status=400)
            
        empleado = get_object_or_404(Empleado.objects.exclude(puesto='ADMIN'), id=empleado_id)
        user = empleado.user
        
        # Baja Lógica
        user.is_active = False
        user.save()
        
        return Response({"message": "Empleado eliminado correctamente"}, 200)