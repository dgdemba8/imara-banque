"""
Django settings for examproject project.
"""

from pathlib import Path
from decouple import config

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent


# ──────────────────────────────────────────────
# SÉCURITÉ
# ──────────────────────────────────────────────

SECRET_KEY = config('SECRET_KEY')

DEBUG = config('DEBUG', default=False, cast=bool)

ALLOWED_HOSTS = config('ALLOWED_HOSTS', default='127.0.0.1,localhost').split(',')




# ──────────────────────────────────────────────
# APPLICATIONS
# ──────────────────────────────────────────────

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Mes applications
    'apps.accounts',
    'apps.dashboard',
    'apps.comptes',
    'apps.transactions',
    'apps.journal',


    # Celery
    'django_celery_beat',
]


MIDDLEWARE = [
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'config.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
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

WSGI_APPLICATION = 'config.wsgi.application'


# ──────────────────────────────────────────────
# La BASE DE DONNÉES
# ──────────────────────────────────────────────

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.mysql',
        'NAME'    : config('DB_NAME'),
        'USER'    : config('DB_USER'),
        'PASSWORD': config('DB_PASSWORD'),
        'HOST'    : config('DB_HOST', default='localhost'),
        'PORT'    : config('DB_PORT', default='3306'),
    }
}


# ──────────────────────────────────────────────
# VALIDATION DES MOTS DE PASSE
# ──────────────────────────────────────────────

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# ──────────────────────────────────────────────
# INTERNATIONALISATION
# ──────────────────────────────────────────────

LANGUAGE_CODE = 'fr-fr'
TIME_ZONE     = 'Africa/Dakar'
USE_I18N      = True
USE_TZ        = True


# ──────────────────────────────────────────────
# FICHIERS STATIQUES
# ──────────────────────────────────────────────

STATIC_URL = '/static/'

STATICFILES_DIRS = [
    BASE_DIR / 'static',
]


# ──────────────────────────────────────────────
# EMAIL
# ──────────────────────────────────────────────

EMAIL_BACKEND       = 'django.core.mail.backends.smtp.EmailBackend'
EMAIL_HOST          = 'smtp.gmail.com'
EMAIL_PORT          = 587
EMAIL_USE_TLS       = True
EMAIL_HOST_USER     = config('EMAIL_HOST_USER')
EMAIL_HOST_PASSWORD = config('EMAIL_HOST_PASSWORD')


# ──────────────────────────────────────────────
# SESSION
# ──────────────────────────────────────────────

SESSION_COOKIE_AGE = 1800


# ──────────────────────────────────────────────
# CELERY
# ──────────────────────────────────────────────

CELERY_BROKER_URL     = config('CELERY_BROKER_URL', default='redis://localhost:6379/0')
CELERY_RESULT_BACKEND = config('CELERY_RESULT_BACKEND', default='redis://localhost:6379/0')
CELERY_TIMEZONE       = 'Africa/Dakar'
CELERY_BEAT_SCHEDULER = 'django_celery_beat.schedulers:DatabaseScheduler'

CELERY_ACCEPT_CONTENT  = ['json']
CELERY_TASK_SERIALIZER = 'json'