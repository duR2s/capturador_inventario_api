import os

BASE_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

# Mantén la clave secreta en variables de entorno en producción
SECRET_KEY = '-_&+lsebec(whhw!%n@ww&1j=4-^j_if9x8$q778+99oz&!ms2'

# -------------------------------------------------------------------------
# SELECTOR DE ENTORNO (PRODUCCIÓN VS DESARROLLO)
# -------------------------------------------------------------------------
# Leemos la variable del sistema. Si no existe, asumimos 'development'
ENVIRONMENT = os.environ.get('DJANGO_ENV', 'development')

if ENVIRONMENT == 'production':
    print("\n------------------------------------------------")
    print(">>> MODO: PRODUCCION (Waitress + Nginx)")
    print("------------------------------------------------\n")
    
    # --- CONFIGURACIÓN DE PRODUCCIÓN ---
    DEBUG = False
    ALLOWED_HOSTS = ["localhost", "127.0.0.1", "192.168.1.50", "*"]
    
    # En prod con Nginx y ruta relativa, CORS es menos estricto o innecesario,
    # pero lo dejamos configurado para aceptar a Nginx en puerto 81.
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:81/api", 
        "http://127.0.0.1:81/api",
        "http://192.168.1.50:81/api"
    ]
    
    # CSRF para producción (aceptar origen de Nginx)
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:81/api", 
        "http://127.0.0.1:81/api",
        "http://192.168.1.50:81/api"
    ]

else:
    print("\n------------------------------------------------")
    print(">>> MODO: DESARROLLO (Runserver)")
    print("------------------------------------------------\n")
    
    # --- CONFIGURACIÓN DE DESARROLLO ---
    DEBUG = True
    ALLOWED_HOSTS = ["*"]
    
    # Angular corre en el 4200 en desarrollo
    CORS_ALLOWED_ORIGINS = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        # Agrega la IP de tu celular si pruebas remoto en dev
        "http://192.168.1.50:4200" 
    ]
    
    CSRF_TRUSTED_ORIGINS = [
        "http://localhost:4200",
        "http://127.0.0.1:4200",
        "http://192.168.1.50:4200" 
    ]

# Permitir credenciales en ambos entornos (necesario para cookies/tokens a veces)
CORS_ALLOW_CREDENTIALS = True

# -------------------------------------------------------------------------
# APLICACIONES Y MIDDLEWARE
# -------------------------------------------------------------------------

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
    'django_q',                       # Django Q2 para tareas en segundo plano
    'capturador_inventario_api',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',     # SIEMPRE AL PRINCIPIO
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'capturador_inventario_api.urls'

# -------------------------------------------------------------------------
# ARCHIVOS ESTÁTICOS Y MEDIA
# -------------------------------------------------------------------------

MEDIA_URL = "/media/"
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

STATIC_URL = "/static/"
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")

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

# -------------------------------------------------------------------------
# BASE DE DATOS
# -------------------------------------------------------------------------

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'OPTIONS': {
            'read_default_file': os.path.join(BASE_DIR, "my.cnf"),
            'charset': 'utf8mb4',
            'init_command': "SET sql_mode='STRICT_TRANS_TABLES'",
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
LANGUAGE_CODE = 'es-mx'
TIME_ZONE = 'America/Mexico_City' 
USE_I18N = True
USE_L10N = True
USE_TZ = True

# -------------------------------------------------------------------------
# REST FRAMEWORK
# -------------------------------------------------------------------------
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
    'DB_FILE': r'SERVIDOR:C:\Microsip datos\REFACCIONES VERGARA.FDB', 
    'USER': 'DJANGOSERVIDOR', 
    'PASSWORD': '123456', 
    'ROLE': 'RDB$ADMIN',
    'CONCEPTOS': {
        'ENTRADA_COMPRA_ID': 1,  
        'ALMACEN_PRINCIPAL_ID': 1 
    },
    'CAMPO_BUSQUEDA_DEFECTO': 'CODIGO_BARRAS' 
}

# -------------------------------------------------------------------------
# DJANGO Q2 CONFIGURATION (Background Tasks)
# -------------------------------------------------------------------------
Q_CLUSTER = {
    'name': 'microsip_sync_cluster',
    'workers': 1,  # IMPORTANTE: Mantener en 1 para evitar conflictos con la DLL de Microsip/Firebird
    'recycle': 500, 
    'timeout': 3600, 
    'retry': 3700, 
    'orm': 'default', 
    'catch_up': False, 
}

# Configuración para evitar el warning models.W042
DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{levelname} {asctime} {module} {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'level': 'DEBUG',
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'loggers': {
        'django': {
            'handlers': ['console'],
            'level': 'INFO',  
            'propagate': True,
        },
        'django.request': {
            'handlers': ['console'],
            'level': 'DEBUG',  
            'propagate': True,
        },
        'capturador_inventario_api': {  
            'handlers': ['console'],
            'level': 'DEBUG',
            'propagate': True,
        },
    },
}