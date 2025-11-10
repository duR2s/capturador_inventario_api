from django.contrib.auth.models import User
from rest_framework import serializers
from .models import Profiles

class UserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "first_name", "last_name", "email")

class ProfilesSerializer(serializers.ModelSerializer):
    user = UserSerializer(read_only=True)
    class Meta:
        model = Profiles
        fields = "__all__"

