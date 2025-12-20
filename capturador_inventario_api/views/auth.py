from django.db.models import *
from capturador_inventario_api.models import *
from capturador_inventario_api.serializers import *
from capturador_inventario_api.models import *
from rest_framework import permissions
from rest_framework import generics
from rest_framework import status
from rest_framework.authtoken.views import ObtainAuthToken
from rest_framework.authtoken.models import Token
from rest_framework.response import Response

class CustomAuthToken(ObtainAuthToken):

    def post(self, request, *args, **kwargs):
        serializer = self.serializer_class(data=request.data,
                                        context={'request': request})

        serializer.is_valid(raise_exception=True)
        user = serializer.validated_data['user']
        
        if user.is_active:
            # 1. Obtener roles de Django Groups
            roles = user.groups.all()
            role_names = [role.name for role in roles]

            # 2. Lógica para definir el 'rol' principal (Singular)
            # Esto es vital para que el frontend sepa si es ADMIN o CAPTURADOR sin procesar arrays
            main_role = None
            
            if 'ADMIN' in role_names:
                main_role = 'ADMIN'
            elif role_names:
                main_role = role_names[0] # Tomar el primero si hay otros
            
            # 3. Fallback: Si no tiene grupos, buscar en el modelo Empleado
            if not main_role:
                try:
                    if hasattr(user, 'empleado'):
                        main_role = user.empleado.puesto
                except Exception:
                    pass

            # Si aun así es nulo, default a user
            if not main_role:
                main_role = 'user'

            token, created = Token.objects.get_or_create(user=user)

            return Response({
                'id': user.pk,
                'first_name': user.first_name,
                'last_name': user.last_name,
                'email': user.email,
                'token': token.key,
                'roles': role_names, 
                'rol': main_role  # <--- CORRECCIÓN CLAVE: Enviamos 'rol' singular
            })
            
        return Response({}, status=status.HTTP_403_FORBIDDEN)


class Logout(generics.GenericAPIView):

    permission_classes = (permissions.IsAuthenticated,)

    def get(self, request, *args, **kwargs):

        print("logout")
        user = request.user
        if user.is_active:
            try:
                token = Token.objects.get(user=user)
                token.delete()
                return Response({'logout':True})
            except Token.DoesNotExist:
                return Response({'logout': False, 'message': 'Token no encontrado'})


        return Response({'logout': False})