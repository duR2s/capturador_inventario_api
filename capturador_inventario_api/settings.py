import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Mantén la clave secreta en variables de entorno en producción
SECRET_KEY = '-_&+lsebec(whhw!%n@ww&1j=4-^j_if9x8$q778+99oz&!ms2'

DEBUG = True  # en desarrollo

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "192.168.0.46"]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django_filters',                 # necesarios para los filtros de DRF
    'rest_framework',
    'rest_framework.authtoken',       # conserva soporte de tokens de DRF
    'corsheaders',                    # librería CORS actualizada
    'django_q',                       # <--- AGREGADO: Django Q2
    'capturador_inventario_api',
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',     # CORS debe ir antes de CommonMiddleware
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

# Configuración de CORS: define orígenes permitidos y quita CORS_ORIGIN_ALLOW_ALL
CORS_ALLOWED_ORIGINS = [
    'http://localhost:4200',
    'http://192.168.0.46:8000'
]
CORS_ALLOW_CREDENTIALS = True

ROOT_URLCONF = 'capturador_inventario_api.urls'

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

STATIC_URL = "/static/"
# STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'capturador_inventario_api.wsgi.application'

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'OPTIONS': {
            'read_default_file': os.path.join(BASE_DIR, "my.cnf"),
            'charset': 'utf8mb4',
        }
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

# -------------------------------------------------------------------------
# CONFIGURACIÓN REGIONAL (MÉXICO - PUEBLA)
# -------------------------------------------------------------------------
LANGUAGE_CODE = 'es-mx'       # Español de México

# America/Mexico_City es la zona horaria correcta para el Tiempo del Centro (Puebla)
TIME_ZONE = 'America/Mexico_City' 

USE_I18N = True
USE_L10N = True

# Mantenemos esto en True. Django guardará en UTC en la BD, 
# pero convertirá a hora de Puebla automáticamente al mostrar datos.
USE_TZ = True


REST_FRAMEWORK = {
    'COERCE_DECIMAL_TO_STRING': False,
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 10,
    'DEFAULT_AUTHENTICATION_CLASSES': (
        'rest_framework.authentication.SessionAuthentication',
        'capturador_inventario_api.models.BearerTokenAuthentication',
    ),
    'DEFAULT_FILTER_BACKENDS': (
        'django_filters.rest_framework.DjangoFilterBackend',
    ),
}


# -------------------------------------------------------------------------
# MICROSIP INTEGRATION SETTINGS
# -------------------------------------------------------------------------

MICROSIP_CONFIG = {
    # CRÍTICO: Usar ruta UNC para el servidor remoto 
    # Ejemplo de producción: r'\\SERVIDOR_MSIP\DATOS_MSIP\Empresa.fdb'
    'DB_FILE': r'192.168.0.30:C:\Microsip datos\REFACCIONES VERGARA.FDB', 
    
    # Usuario y contraseña de Firebird/Microsip (Codificados a latin-1 en el servicio)
    'USER': 'DJANGOSERVIDOR', 
    'PASSWORD': '123456', 
    
    # Configuración de los IDs internos de Microsip 
    'CONCEPTOS': {
        'ENTRADA_COMPRA_ID': 1,  
        'ALMACEN_PRINCIPAL_ID': 1 
    },
    
    # Campo a usar para la búsqueda rápida en la BD de Microsip
    'CAMPO_BUSQUEDA_DEFECTO': 'CODIGO_BARRAS' 
}

# -------------------------------------------------------------------------
# DJANGO Q2 CONFIGURATION (Background Tasks)
# -------------------------------------------------------------------------
Q_CLUSTER = {
    'name': 'microsip_sync_cluster',
    'workers': 1,  # IMPORTANTE: Mantener en 1 para evitar conflictos con la DLL de Microsip/Firebird
    'recycle': 500, # Reinicia el worker después de 500 tareas para liberar memoria (útil con DLLs)
    'timeout': 3600, # 1 hora de timeout (la sincronización puede ser lenta)
    'retry': 3700, # Debe ser mayor que el timeout
    'orm': 'default', # Usa la BD de Django como broker
    'catch_up': False, # Si el cluster se cae, no intentar ejecutar todas las tareas perdidas de golpe
}

# Configuración para evitar el warning models.W042
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'