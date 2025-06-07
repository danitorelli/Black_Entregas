"""
Django settings for cardapio_config project.

For more information on this file, see
https://docs.djangoproject.com/en/5.2/topics/settings/

For the full list of settings and their values, see
https://docs.djangoproject.com/en/5.2/ref/settings/
"""

from pathlib import Path
from decouple import config # Importa config
import os # Importa os (já necessário para os.path.join)
# dj_database_url não é necessário se você usa config() para o BD
# import dj_database_url 

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/5.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY_DJANGO') # Carrega do .env

# SECURITY WARNING: don't run with debug turned on in production!
# Usa uma lambda para converter 'TRUE'/'FALSE' do .env para booleanos Python
DEBUG = config('DEBUG_DJANGO', default=False, cast=lambda x: str(x).lower() == 'true') 

# Define ALLOWED_HOSTS com base no modo DEBUG
if DEBUG:
    ALLOWED_HOSTS = ['*'] # Permite qualquer host em desenvolvimento
else:
    # Em produção, substitua com os domínios reais (ex: ['danitorelli.pythonanywhere.com', 'seusite.com'])
    ALLOWED_HOSTS = ['127.0.0.1', 'localhost'] # Padrão seguro para não debug, você vai querer mudar isso no deploy
    #ALLOWED_HOSTS = ['seu_ip_publico_ec2', 'seu_nome_dns_ec2.amazonaws.com', 'seu-dominio.com']
    # Exemplo para PythonAnywhere: ALLOWED_HOSTS = ['danitorelli.pythonanywhere.com', '127.0.0.1']


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles', # Necessário para collectstatic e servir arquivos estáticos do admin
    'menu', #nosso app
    #'widget_tweaks', # Descomente se for usar
]

MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    # 'whitenoise.middleware.WhiteNoiseMiddleware', # Descomente e configure WhiteNoise APENAS para deploy em produção
]

ROOT_URLCONF = 'cardapio_config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'cardapio_config.wsgi.application'


# Database
# https://docs.djangoproject.com/en/5.2/ref/settings/#databases

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': config('DATABASE_NAME'),
        'USER': config('DATABASE_USER'),
        'PASSWORD': config('DATABASE_PASSWORD'),
        'HOST': config('DATABASE_HOST'),
        'PORT': config('DATABASE_PORT'),
    }
}
# A linha dj_database_url comentada é desnecessária se você já usa config() acima para PostgreSQL.
# DATABASES = {
#    "default": dj_database_url.config(default=os.environ.get("DATABASE_URL"))
# }


# Password validation
# https://docs.djangoproject.com/en/5.2/ref/settings/#auth-password-validators

AUTH_PASSWORD_VALIDATORS = [
    {
        'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator',
    },
    {
        'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator',
    },
]


# Internationalization
# https://docs.djangoproject.com/en/5.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC' # Você pode mudar para 'America/Sao_Paulo' para fuso horário brasileiro

USE_I18N = True

USE_TZ = True

# AWS S3 Settings (adicione essas linhas)
AWS_ACCESS_KEY_ID = config('AWS_ACCESS_KEY_ID')
AWS_SECRET_ACCESS_KEY = config('AWS_SECRET_ACCESS_KEY')
AWS_STORAGE_BUCKET_NAME = config('AWS_STORAGE_BUCKET_NAME')
AWS_S3_REGION_NAME = 'us-east-1' # Substitua pela sua região (ex: sa-east-1 para SP)
AWS_S3_SIGNATURE_VERSION = 's3v4'
AWS_S3_FILE_OVERWRITE = False
AWS_DEFAULT_ACL = None # Ou 'public-read' se quiser arquivos publicamente acessíveis
AWS_QUERYSTRING_AUTH = False # Evita query strings na URL (limpa)
AWS_HEADERS = {
    'Cache-Control': 'max-age=86400', # Cache para arquivos estáticos por 1 dia
}

# Configuração de Storages
DEFAULT_FILE_STORAGE = 'storages.backends.s3boto3.S3Boto3Storage'
STATICFILES_STORAGE = 'storages.backends.s3boto3.S3StaticStorage'

#URLs dos arquivos estáticos e de mídia (apontam para o S3)
STATIC_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/static/"
MEDIA_URL = f"https://{AWS_STORAGE_BUCKET_NAME}.s3.{AWS_S3_REGION_NAME}.amazonaws.com/media/"



# Static files (CSS, JavaScript, Images)
# https://docs.djangoproject.com/en/5.2/howto/static-files/

#STATIC_URL = '/static/'
# STATICFILES_DIRS informa ao Django onde procurar seus arquivos estáticos em desenvolvimento
STATICFILES_DIRS = [
    BASE_DIR / 'static', # Para arquivos estáticos globais do projeto (se você tiver)
    BASE_DIR / 'menu/static', # O Django já encontra estáticos dentro de apps, mas manter se tiver específicos
]
# STATIC_ROOT é a pasta de destino para 'python manage.py collectstatic'
STATIC_ROOT = BASE_DIR / 'staticfiles_collected' 


# Media files (user uploads like product images)
#MEDIA_URL = '/media/'
MEDIA_ROOT = BASE_DIR / 'mediafiles' # Base directory for user-uploaded files


# Default primary key field type
# https://docs.djangoproject.com/en/5.2/ref/settings/#default-auto-field

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'


# Session settings for cart persistence
SESSION_EXPIRE_AT_BROWSER_CLOSE = False # A sessão NÃO expira ao fechar o navegador
SESSION_COOKIE_AGE = 30 * 60 # 30 minutos em segundos (1800 segundos)

# Configurações adicionais para robustez da sessão em DESENVOLVIMENTO (para localhost)
SESSION_COOKIE_SAMESITE = 'Lax' # Permite que o cookie seja enviado em navegações do mesmo site.
SESSION_COOKIE_SECURE = False # DEVE SER False em ambiente de desenvolvimento (HTTP)
SESSION_COOKIE_HTTPONLY = True # Boa prática de segurança (não acessível via JS do cliente)
CSRF_COOKIE_SAMESITE = 'Lax' # Configuração similar para cookies CSRF
CSRF_COOKIE_SECURE = False # DEVE SER False em ambiente de desenvolvimento (HTTP)

# Para garantir que o cookie CSRF seja enviado para localhost (se DEBUG=True)
CSRF_TRUSTED_ORIGINS = ['http://localhost', 'http://127.0.0.1']

# Variáveis para a API do WhatsApp (pegas do .env)
WHATSAPP_NUMBER = config('WHATSAPP_NUMBER') 

# WHATSAPP_API_URL = config('WHATSAPP_API_URL', default='') # Se for usar API paga, defina aqui
# WHATSAPP_API_TOKEN = config('WHATSAPP_API_TOKEN', default='')
# WHATSAPP_SENDER_NUMBER = config('WHATSAPP_SENDER_NUMBER', default='')