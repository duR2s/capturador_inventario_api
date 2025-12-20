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

class EmpleadoAll(generics.CreateAPIView):
    permission_classes = (permissions.IsAuthenticated,)
    
    def get(self, request, *args, **kwargs):
        empleados = Empleado.objects.exclude(puesto='ADMIN').filter(user__is_active=True).order_by("id")
        lista = EmpleadoSerializer(empleados, many=True).data
        return Response(lista, 200)

class EmpleadoView(generics.CreateAPIView):
    
    def get_permissions(self):
        if self.request.method == 'POST':
            return [permissions.AllowAny()] 
        return [permissions.IsAuthenticated()]
    
    def get(self, request, *args, **kwargs):
        empleado_id = request.GET.get("id")
        if not empleado_id:
            return Response({"error": "ID es requerido"}, status=400)
        
        empleado = get_object_or_404(Empleado.objects.exclude(puesto='ADMIN'), id=empleado_id)
        data = EmpleadoSerializer(empleado, many=False).data
        return Response(data, 200)
    
    @transaction.atomic
    def post(self, request, *args, **kwargs):
        """Crear nuevo empleado con puesto controlado"""
        data = request.data.copy()
        
        if 'email' in data and 'username' not in data:
            data['username'] = data['email']

        user_serializer = UserSerializer(data=data)
        
        if user_serializer.is_valid():
            # CORRECCIÓN: Validación estricta del puesto
            puesto_recibido = data.get('puesto', 'CAPTURADOR')
            puestos_permitidos = ['CAPTURADOR', 'OTRO'] # ADMIN no permitido aquí
            
            if puesto_recibido not in puestos_permitidos:
                # Si envían algo raro, lo forzamos a CAPTURADOR por seguridad
                puesto = 'CAPTURADOR'
            else:
                puesto = puesto_recibido
            
            # --- LÓGICA DE EDAD AUTOMÁTICA ---
            fecha_nac = data.get("fecha_nacimiento")
            edad_calculada = calcular_edad(fecha_nac)
            
            first_name = data.get('first_name')
            last_name = data.get('last_name')
            email = data.get('email')
            password = data.get('password')

            if User.objects.filter(email=email).exists():
                return Response({"message": f"El email {email} ya está registrado"}, 400)

            # 1. Crear Usuario
            user = User.objects.create(
                username=email,
                email=email,
                first_name=first_name,
                last_name=last_name,
                is_active=True
            )
            
            user.set_password(password)
            user.save()

            # 2. Asignar grupo (usando el puesto normalizado)
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
                edad=edad_calculada,
                puesto=puesto # Guardamos el puesto normalizado
            )
            
            return Response({"empleado_created_id": empleado.id}, 201)

        return Response(user_serializer.errors, status=status.HTTP_400_BAD_REQUEST)

    @transaction.atomic
    def put(self, request, *args, **kwargs):
        """Actualizar empleado existente"""
        empleado_id = request.data.get("id")
        if not empleado_id:
             return Response({"error": "ID es requerido para actualizar"}, status=400)

        empleado = get_object_or_404(Empleado.objects.exclude(puesto='ADMIN'), id=empleado_id)
        
        nuevo_puesto = request.data.get("puesto")
        # Validación al actualizar también
        if nuevo_puesto:
            if nuevo_puesto == 'ADMIN':
                return Response({"error": "No se puede promover a ADMIN desde esta vista"}, 403)
            
            if nuevo_puesto in ['CAPTURADOR', 'OTRO'] and empleado.puesto != nuevo_puesto:
                antiguo_grupo = Group.objects.filter(name=empleado.puesto).first()
                if antiguo_grupo:
                    antiguo_grupo.user_set.remove(empleado.user)
                
                nuevo_grupo, _ = Group.objects.get_or_create(name=nuevo_puesto)
                nuevo_grupo.user_set.add(empleado.user)
                
                empleado.puesto = nuevo_puesto

        nueva_fecha = request.data.get("fecha_nacimiento")
        if nueva_fecha:
            empleado.fecha_nacimiento = nueva_fecha
            nueva_edad = calcular_edad(nueva_fecha)
            if nueva_edad is not None:
                empleado.edad = nueva_edad

        if request.data.get("clave_interna"):
            empleado.clave_interna = request.data.get("clave_interna")
            
        empleado.telefono = request.data.get("telefono", empleado.telefono)
        empleado.rfc = request.data.get("rfc", empleado.rfc)
        
        empleado.save()
        
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
        user.is_active = False
        user.save()
        
        return Response({"message": "Empleado eliminado correctamente"}, 200)