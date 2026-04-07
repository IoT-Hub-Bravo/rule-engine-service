from pathlib import Path
import os
from decouple import config, Csv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# Quick-start development settings - unsuitable for production
# See https://docs.djangoproject.com/en/4.2/howto/deployment/checklist/

# SECURITY WARNING: keep the secret key used in production secret!
SECRET_KEY = config('SECRET_KEY')

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='localhost,127.0.0.1,web', cast=Csv())


# Application definition

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
]

# Third party apps
INSTALLED_APPS += [
    'corsheaders',
    'channels',
    'django_prometheus',
    'django_celery_beat',
]
# Local apps
INSTALLED_APPS += [
    'apps.rules.apps.RulesConfig',
]

MIDDLEWARE = [
    'django_prometheus.middleware.PrometheusBeforeMiddleware',
    'config.middleware.logging_middleware.LoggingMiddleware',  # Logging middleware
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'django_prometheus.middleware.PrometheusAfterMiddleware',
]

ROOT_URLCONF = 'config.urls'

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

WSGI_APPLICATION = 'config.wsgi.application'


# Databases
IS_BUILD = os.environ.get('BUILD_TIME') == '1'

if IS_BUILD:
    DATABASES = {
        "default": {
            "ENGINE": "django.db.backends.sqlite3",
            "NAME": "/tmp/db.sqlite3",
        }
    }
else:
    DATABASES = {
        'default': {
            'ENGINE': 'django.db.backends.postgresql',
            'NAME': config('DB_NAME'),
            'USER': config('DB_USER'),
            'PASSWORD': config('DB_PASSWORD'),
            'HOST': config('DB_HOST', default='localhost'),
            'PORT': config('DB_PORT', default='5432', cast=int),
        },
    }


# Password validation
# https://docs.djangoproject.com/en/4.2/ref/settings/#auth-password-validators

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
# https://docs.djangoproject.com/en/4.2/topics/i18n/

LANGUAGE_CODE = 'en-us'

TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True


# Static files (CSS, JavaScript, Images)

STATIC_URL = 'static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

# Default primary key field type

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)

CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS', default='', cast=lambda v: v.split(',') if v else []
)
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_ALL_ORIGINS = config('CORS_ALLOW_ALL_ORIGINS', default=False, cast=bool)

CORS_ALLOWED_ORIGINS = config(
    'CORS_ALLOWED_ORIGINS', default='http://localhost:3000,http://localhost:5173', cast=Csv()
)

CORS_ALLOW_CREDENTIALS = True

CORS_ALLOW_METHODS = [
    'DELETE',
    'GET',
    'OPTIONS',
    'PATCH',
    'POST',
    'PUT',
]

CORS_ALLOW_HEADERS = [
    'accept',
    'accept-encoding',
    'authorization',
    'content-type',
    'dnt',
    'origin',
    'user-agent',
    'x-csrftoken',
    'x-requested-with',
]

# Redis config
REDIS_HOST = config('REDIS_HOST', default='redis')
REDIS_PORT = config('REDIS_PORT', default=6379)
REDIS_PASSWORD = config('REDIS_PASSWORD', default=None)
REDIS_DECODE_RESPONSES = config('REDIS_DECODE_RESPONSES', default = True)

REDIS_CONFIG = {
    "host": REDIS_HOST,
    "port": REDIS_PORT,
    "password": REDIS_PASSWORD,
    "decode_responses": REDIS_DECODE_RESPONSES,
}

# LOGGING configuration for django and celery
DJANGO_ROOT_LOG_LEVEL = config('DJANGO_ROOT_LOG_LEVEL', default='INFO')
DJANGO_LOG_LEVEL = config('DJANGO_LOG_LEVEL', default='INFO')
CELERY_LOG_LEVEL = config('CELERY_LOG_LEVEL', default='INFO')
RULE_PROCESSOR_LOG_LEVEL = config('RULE_PROCESSOR_LOG_LEVEL', default='INFO')
LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "json": {
            "()": 'pythonjsonlogger.jsonlogger.JsonFormatter',
            "format": "{asctime} {levelname} {name} {message} {request_id} {duration}",
            "style": "{",
            "rename_fields": {
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger_name",
            },
        },

        "celery_json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "{asctime} {levelname} {name} {message} {task_id} {task_name}",
            "style": "{",
            "rename_fields": {
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger_name",
            },
        },

        "rule_processor_json": {
            "()": "pythonjsonlogger.jsonlogger.JsonFormatter",
            "format": "{asctime} {levelname} {name} {message}",
            "style": "{",
            "rename_fields": {
                "asctime": "timestamp",
                "levelname": "level",
                "name": "logger_name",
            },
        },

    },

    "filters": {
        "request_context": {
            "()": "config.filters.logging_filters.RequestContextFilter",
        },
        "celery_context": {
            "()": "config.filters.logging_filters.CeleryContextFilter",
        },
    },

    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "filters": ["request_context"],
            "formatter": "json",
        },

        "celery_console": {
            "class": "logging.StreamHandler",
            "filters": ["celery_context"],
            "formatter": "celery_json",
        },

        "rule_processor_console": {
            "class": "logging.StreamHandler",
            "formatter": "rule_processor_json",
        },
    },

    "loggers": {
        "": {
            "handlers": ["console"],
            "level": DJANGO_ROOT_LOG_LEVEL,
        },

        "django": {  # Django logger is declared (propagate = False by default)
            "handlers": ["console"],
            "level": DJANGO_LOG_LEVEL,
            "propagate": False,
        },

        "celery": {
            "handlers": ["celery_console"],
            "level": CELERY_LOG_LEVEL,
            "propagate": False,
        },

        "apps.rules.services.rule_processor": {
            "handlers": ["rule_processor_console"],
            "level": RULE_PROCESSOR_LOG_LEVEL,
            "propagate": False,
        },
    },
}