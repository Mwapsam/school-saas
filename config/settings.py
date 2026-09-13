import os
import re
from pathlib import Path
import base64
from django.core.exceptions import ImproperlyConfigured

BASE_DIR = Path(__file__).resolve().parent.parent

from django.urls import reverse_lazy
from django.utils.translation import gettext_lazy as _

_IS_PRODUCTION = os.getenv("DJANGO_ENV", "development").lower() == "production"

_INSECURE_SECRET_KEY = "django-insecure-04p@%t4gven4uvy!eb)o2)e=e*k@7no3@7hae=a=ms0l3t)-2j"
SECRET_KEY = os.getenv("SECRET_KEY", _INSECURE_SECRET_KEY)

if _IS_PRODUCTION and (not os.getenv("SECRET_KEY") or SECRET_KEY == _INSECURE_SECRET_KEY):
    raise ImproperlyConfigured(
        "SECRET_KEY environment variable must be set to a unique secret value in production."
    )

DEBUG = os.getenv("DEBUG", "False").lower() == "true"

# DEBUG must never be enabled in production.
if _IS_PRODUCTION and DEBUG:
    raise ImproperlyConfigured("DEBUG must be False in production (set DEBUG=False).")

SHARED_APPS = [
    "django_tenants",
    "tenant_users",
    "tenant_users.tenants",
    "core",  # Must come before unfold so custom templates are found first

    "unfold",
    "unfold.contrib.filters",
    "unfold.contrib.forms",
    "unfold.contrib.inlines",

    "django.contrib.contenttypes",
    "django.contrib.auth",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.admin",
    "rest_framework",
    "rest_framework_simplejwt",
    "drf_spectacular",
    "corsheaders",
    "django_filters",
    "storages",
    "portal",
]

TENANT_APPS = [
    "unfold",
    'django.contrib.admin',
    'tenant_users.permissions',
]

INSTALLED_APPS = list(SHARED_APPS) + [app for app in TENANT_APPS if app not in SHARED_APPS]

TENANT_MODEL = 'core.School'
TENANT_DOMAIN_MODEL = 'core.Domain'
SHOW_PUBLIC_IF_NO_TENANT_FOUND = True

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django_tenants.middleware.main.TenantMainMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'whitenoise.middleware.WhiteNoiseMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'tenant_users.tenants.middleware.TenantAccessMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
    'core.middleware.DashboardAccessMiddleware',
]

# URL of the Next.js parent/teacher portal — teachers and parents are gated
# out of the Django dashboard (core.middleware.DashboardAccessMiddleware) and
# pointed here instead.
PORTAL_APP_URL = os.getenv("PORTAL_APP_URL", "http://localhost:3000")


ROOT_URLCONF = 'config.urls'


TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / "templates"],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'core.authz.context.authz',
                'core.context_processors.terminology',
            ],
        },
    },
]

WSGI_APPLICATION = 'config.wsgi.application'

DATABASES = {
    "default": {
        "ENGINE": os.environ.get("DATABASE_ENGINE", "django_tenants.postgresql_backend"),
        "NAME": os.environ.get("DATABASE_NAME", "school_db"),
        "USER": os.environ.get("DATABASE_USER", "school_user"),
        "PASSWORD": os.environ.get("DATABASE_PASSWORD", "school_pass"),
        "HOST": os.environ.get("DATABASE_HOST", 'db'),
        "PORT": os.environ.get("DATABASE_PORT", '5432'),
        "CONN_MAX_AGE": 600,
        "OPTIONS": {
            "connect_timeout": 10,
            "options": "-c statement_timeout=30000",
        },
    }
}

BASE_DOMAIN = os.getenv("BASE_DOMAIN", "localhost")
PUBLIC_SCHEMA_NAME = "public"
DATABASE_ROUTERS = ['django_tenants.routers.TenantSyncRouter']
TENANT_USERS_DOMAIN = os.getenv('TENANT_USERS_DOMAIN', 'localhost')


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

LANGUAGE_CODE = 'en-us'

# PRODUCTIZATION: Global default is UTC (neutral).
# Per-tenant timezone is configured via School.timezone field.
# Middleware can override this per-request based on tenant configuration.
TIME_ZONE = 'UTC'

USE_I18N = True

USE_TZ = True

ENVIRONMENT = os.getenv("DJANGO_ENV", "development").lower()
IS_PRODUCTION = ENVIRONMENT == "production"
IS_STAGING = ENVIRONMENT == "staging"

STATICFILES_DIRS = [BASE_DIR / "static"]
STATIC_ROOT = os.path.join(BASE_DIR, "staticfiles")
MEDIA_ROOT = os.path.join(BASE_DIR, "media")

USE_S3 = os.getenv(
    "USE_S3", "true" if ENVIRONMENT in ("staging", "production") else "false"
).lower() == "true"

raw = os.getenv("CLOUDFRONT_PRIVATE_KEY_B64")

if USE_S3:
    AWS_S3_REGION_NAME = os.getenv("AWS_S3_REGION_NAME", "ap-southeast-1")
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID") or None
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY") or None

    AWS_PUBLIC_BUCKET_NAME = os.environ["AWS_PUBLIC_BUCKET_NAME"]
    AWS_PRIVATE_BUCKET_NAME = os.environ["AWS_PRIVATE_BUCKET_NAME"]

    CLOUDFRONT_KEY_ID = os.getenv("CLOUDFRONT_KEY_ID") or None

    AWS_PUBLIC_CLOUDFRONT_DOMAIN = os.environ["AWS_PUBLIC_CLOUDFRONT_DOMAIN"]
    AWS_PRIVATE_CLOUDFRONT_DOMAIN = os.environ["AWS_PRIVATE_CLOUDFRONT_DOMAIN"]

    _cf_key_b64 = os.getenv("CLOUDFRONT_PRIVATE_KEY_B64")
    _cf_key_file = os.getenv("CLOUDFRONT_PRIVATE_KEY_FILE")

    if _cf_key_b64:
        CLOUDFRONT_PRIVATE_KEY = base64.b64decode(_cf_key_b64).decode()
    elif _cf_key_file:
        with open(_cf_key_file) as f:
            CLOUDFRONT_PRIVATE_KEY = f.read()
    else:
        CLOUDFRONT_PRIVATE_KEY = None

    if CLOUDFRONT_KEY_ID and not CLOUDFRONT_PRIVATE_KEY:
        raise ImproperlyConfigured(
            "CLOUDFRONT_KEY_ID is set but no private key was provided. "
            "Set CLOUDFRONT_PRIVATE_KEY_B64 or CLOUDFRONT_PRIVATE_KEY_FILE."
        )

    CLOUDFRONT_SIGNED_URL_EXPIRY = int(os.getenv("CLOUDFRONT_SIGNED_URL_EXPIRY", "3600"))

    # ── Shared S3 behaviour ──
    AWS_S3_SIGNATURE_VERSION = "s3v4"
    AWS_DEFAULT_ACL = None
    AWS_S3_FILE_OVERWRITE = False
    AWS_QUERYSTRING_AUTH = False
    AWS_S3_OBJECT_PARAMETERS = {"CacheControl": "max-age=86400"}

    STORAGES = {
        "default":     {"BACKEND": "core.storage_backends.PublicMediaStorage"},
        "public":      {"BACKEND": "core.storage_backends.PublicMediaStorage"},
        "staticfiles": {"BACKEND": "core.storage_backends.StaticStorage"},
    }

    STATIC_URL = f"https://{AWS_PUBLIC_CLOUDFRONT_DOMAIN}/static/"
    MEDIA_URL = f"https://{AWS_PUBLIC_CLOUDFRONT_DOMAIN}/media/"  # public media; private URLs are signed
else:
    # ── Development: local filesystem ──
    STATIC_URL = "/static/"
    MEDIA_URL = "/media/"
    _static_backend = (
        "django.contrib.staticfiles.storage.StaticFilesStorage"
        if DEBUG
        else "whitenoise.storage.CompressedManifestStaticFilesStorage"
    )
    STORAGES = {
        "default":     {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "public":      {"BACKEND": "django.core.files.storage.FileSystemStorage"},
        "staticfiles": {"BACKEND": _static_backend},
    }

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

LOGIN_URL = '/accounts/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/accounts/login/'

AUTH_USER_MODEL = 'core.User'

AUTHENTICATION_BACKENDS = ("tenant_users.permissions.backend.UserBackend",)


REST_FRAMEWORK = {
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
        'rest_framework.authentication.BasicAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
    'DEFAULT_PAGINATION_CLASS': 'rest_framework.pagination.PageNumberPagination',
    'PAGE_SIZE': 20,
    'DEFAULT_FILTER_BACKENDS': [
        'django_filters.rest_framework.DjangoFilterBackend',
        'rest_framework.filters.SearchFilter',
        'rest_framework.filters.OrderingFilter',
    ],
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_SCHEMA_CLASS': 'drf_spectacular.openapi.AutoSchema',
    'EXCEPTION_HANDLER': 'core.api_exception_handler.service_exception_handler',
    'TEST_REQUEST_DEFAULT_FORMAT': 'json',
}

# drf-spectacular schema generation for OpenAPI documentation
SPECTACULAR_SETTINGS = {
    'TITLE': 'School Management Platform API',
    'DESCRIPTION': 'API for school management including academics, finance, HR, admissions, and operations',
    'VERSION': '1.0.0',
    'SERVE_PERMISSIONS': ['rest_framework.permissions.IsAuthenticated'],
    'SCHEMA_PATH_PREFIX': r'/api/v1',
    'TAGS_PATH': '/api/tags/',
}

if DEBUG:
    REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'].append('rest_framework.renderers.BrowsableAPIRenderer')

if not DEBUG:
    SECURE_HSTS_SECONDS = 31536000
    SECURE_SSL_REDIRECT = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    USE_X_FORWARDED_HOST = True
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    X_FRAME_OPTIONS = "DENY"
    DATA_UPLOAD_MAX_MEMORY_SIZE = 10485760  
    FILE_UPLOAD_MAX_MEMORY_SIZE = 10485760  
else:
    SECURE_HSTS_SECONDS = 0
    SECURE_SSL_REDIRECT = False
    SESSION_COOKIE_SECURE = False
    CSRF_COOKIE_SECURE = False
    SECURE_HSTS_INCLUDE_SUBDOMAINS = False
    SECURE_HSTS_PRELOAD = False
    DATA_UPLOAD_MAX_MEMORY_SIZE = 104857600  
    FILE_UPLOAD_MAX_MEMORY_SIZE = 104857600  

_allowed_hosts_env = os.getenv("ALLOWED_HOSTS")
if _IS_PRODUCTION and not _allowed_hosts_env:
    raise ImproperlyConfigured("ALLOWED_HOSTS must be set in production.")
ALLOWED_HOSTS = (_allowed_hosts_env or "localhost,127.0.0.1").split(",")

CSRF_TRUSTED_ORIGINS = []
if BASE_DOMAIN and BASE_DOMAIN != "localhost":
    CSRF_TRUSTED_ORIGINS += [f"https://{BASE_DOMAIN}", f"https://*.{BASE_DOMAIN}"]
if TENANT_USERS_DOMAIN and TENANT_USERS_DOMAIN not in ("localhost", BASE_DOMAIN):
    CSRF_TRUSTED_ORIGINS += [f"https://{TENANT_USERS_DOMAIN}", f"https://*.{TENANT_USERS_DOMAIN}"]


logs_dir = os.path.join(BASE_DIR, "logs")
if not os.path.exists(logs_dir):
    os.makedirs(logs_dir, exist_ok=True)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {
            "format": "{levelname} {asctime} {name} {process:d} {thread:d} {message}",
            "style": "{",
        },
        "simple": {
            "format": "{levelname} {message}",
            "style": "{",
        },
    },
    "handlers": {
        "console": {
            "level": "DEBUG" if DEBUG else "INFO",
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "root": {
        "handlers": ["console"],
        "level": "INFO",
    },
    "loggers": {
        "django": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
        "core": {
            "handlers": ["console"],
            "level": "DEBUG" if DEBUG else "INFO",
            "propagate": False,
        },
    },
}
if (
    not os.environ.get("PYTEST_CURRENT_TEST")
    and os.path.exists(logs_dir)
    and os.access(logs_dir, os.W_OK)
):
    LOGGING["handlers"]["file"] = {
        "level": "INFO",
        "class": "logging.handlers.RotatingFileHandler",
        "filename": os.path.join(logs_dir, "django.log"),
        "maxBytes": 1024 * 1024 * 10,  
        "backupCount": 5,
        "formatter": "verbose",
    }
    LOGGING["root"]["handlers"].append("file")
    LOGGING["loggers"]["django"]["handlers"].append("file")
    LOGGING["loggers"]["core"]["handlers"].append("file")
else:
    import logging

    logging.warning("File logging is disabled due to permissions or directory issues.")


# Key for core.db_fields.EncryptedTextField (QuickBooks client secret + OAuth
# tokens at rest). Falls back to SECRET_KEY when unset; set a dedicated, stable
# value in production - rotating it makes existing ciphertext unreadable.
FIELD_ENCRYPTION_KEY = os.getenv("FIELD_ENCRYPTION_KEY", "")
if _IS_PRODUCTION and not FIELD_ENCRYPTION_KEY:
    import warnings
    warnings.warn(
        "FIELD_ENCRYPTION_KEY is not set - encrypted fields will fall back to "
        "SECRET_KEY. Set a dedicated key so credentials survive a SECRET_KEY rotation."
    )

QUICKBOOKS_AUTO_SYNC_ENABLED = os.getenv("QUICKBOOKS_AUTO_SYNC_ENABLED", "True").lower() == "true"
QUICKBOOKS_WEBHOOK_VERIFIER_TOKEN = os.getenv("QUICKBOOKS_WEBHOOK_VERIFIER_TOKEN", "")
if _IS_PRODUCTION and not QUICKBOOKS_WEBHOOK_VERIFIER_TOKEN:
    import warnings
    warnings.warn(
        "QUICKBOOKS_WEBHOOK_VERIFIER_TOKEN is not set - QuickBooks webhook "
        "notifications will be rejected until it is configured."
    )
BASE_URL = os.getenv("BASE_URL")
if _IS_PRODUCTION and not BASE_URL:
    raise ImproperlyConfigured(
        "BASE_URL must be set in production (used for emails, OAuth callbacks, and report links)."
    )
BASE_URL = BASE_URL or "http://localhost:8000"

CELERY_BROKER_URL = os.getenv("CELERY_BROKER_URL", "redis://redis:6379/0")
CELERY_RESULT_BACKEND = os.getenv("CELERY_RESULT_BACKEND", "redis://redis:6379/0")
CELERY_ACCEPT_CONTENT = ['json']
CELERY_TASK_SERIALIZER = 'json'
CELERY_RESULT_SERIALIZER = 'json'
CELERY_TIMEZONE = TIME_ZONE
CELERY_ENABLE_UTC = True
CELERY_TASK_TRACK_STARTED = True
CELERY_TASK_TIME_LIMIT = 30 * 60  # 30 minutes (hard limit)
CELERY_TASK_SOFT_TIME_LIMIT = 25 * 60  # raise SoftTimeLimitExceeded before the hard kill
CELERY_WORKER_PREFETCH_MULTIPLIER = 1
CELERY_WORKER_MAX_TASKS_PER_CHILD = 50
CELERY_TASK_ACKS_LATE = True
CELERY_TASK_REJECT_ON_WORKER_LOST = True

CACHES = {
    "default": {
        "BACKEND": "django_redis.cache.RedisCache",
        "LOCATION": os.getenv("REDIS_CACHE_URL", "redis://redis:6379/2"),
        "OPTIONS": {
            "CLIENT_CLASS": "django_redis.client.DefaultClient",
            "SOCKET_CONNECT_TIMEOUT": 5,
            "SOCKET_TIMEOUT": 5,
            # A cache outage must degrade to a DB hit, never 500 the request.
            "IGNORE_EXCEPTIONS": True,
        },
        "KEY_PREFIX": os.getenv("CACHE_KEY_PREFIX", "school-platform"),
        "TIMEOUT": 300,
    }
}
DJANGO_REDIS_IGNORE_EXCEPTIONS = True
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# ── Email Configuration ──
EMAIL_BACKEND = os.getenv("EMAIL_BACKEND", "django.core.mail.backends.smtp.EmailBackend")
EMAIL_HOST = os.getenv("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.getenv("EMAIL_PORT", "587"))
EMAIL_USE_TLS = os.getenv("EMAIL_USE_TLS", "True").lower() == "true"
EMAIL_HOST_USER = os.getenv("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.getenv("EMAIL_HOST_PASSWORD", "")
DEFAULT_FROM_EMAIL = os.getenv("DEFAULT_FROM_EMAIL", EMAIL_HOST_USER)
SERVER_EMAIL = os.getenv("SERVER_EMAIL", EMAIL_HOST_USER)

DATA_UPLOAD_MAX_NUMBER_FIELDS = 100000
from datetime import timedelta  # noqa: E402

SIMPLE_JWT = {
    "ACCESS_TOKEN_LIFETIME": timedelta(
        minutes=int(os.getenv("JWT_ACCESS_MINUTES", "30"))
    ),
    "REFRESH_TOKEN_LIFETIME": timedelta(
        days=int(os.getenv("JWT_REFRESH_DAYS", "7"))
    ),
    "ROTATE_REFRESH_TOKENS": True,
    "BLACKLIST_AFTER_ROTATION": False,
    "UPDATE_LAST_LOGIN": True,
    "USER_ID_FIELD": "id",
    "USER_ID_CLAIM": "user_id",
    "AUTH_HEADER_TYPES": ("Bearer",),
}


from corsheaders.defaults import default_headers, default_methods
CORS_ALLOW_CREDENTIALS = True

CORS_ALLOWED_ORIGINS = [
    "http://localhost:3000",
    "http://127.0.0.1:3000",
] + [
    origin.strip()
    for origin in os.getenv("CORS_ALLOWED_ORIGINS", "").split(",")
    if origin.strip()
]

CORS_ALLOW_METHODS = list(default_methods)
CORS_ALLOW_HEADERS = list(default_headers) + [
    "Authorization",
    # Client-app identification for the Manage Clients gate (portal.client_gate).
    "x-client-app",
    "x-client-app-version",
]

CORS_ALLOWED_ORIGIN_REGEXES = [r"^http://[a-z0-9-]+\.localhost:3000$"]
if BASE_DOMAIN and BASE_DOMAIN != "localhost":
    CORS_ALLOWED_ORIGIN_REGEXES.append(
        rf"^https://[a-z0-9-]+\.{re.escape(BASE_DOMAIN)}$"
    )

# settings.py

UNFOLD = {
    "SITE_TITLE": os.getenv("ADMIN_SITE_TITLE", "Admin Dashboard"),
    "SITE_HEADER": os.getenv("ADMIN_SITE_HEADER", "School Management Platform"),
    "SITE_URL": "/",
    "SITE_SUBHEADER": "Operations Console",
    "SITE_SYMBOL": "school",  # Material Symbols icon name
    "SHOW_HISTORY": True,
    "SHOW_VIEW_ON_SITE": False,

    "SITE_LOGO": {
        "light": "/static/img/logo.png",
        "dark": "/static/img/logo.png",
    },

        "SITE_ICON": {
        "light": "/static/img/logo.png",
        "dark": "/static/img/logo.png",
    },

    "SITE_FAVICONS": [
        {
            "href": "/static/img/logo.png",
            "rel": "icon",
            "type": "image/x-icon",
        },
        {
            "href": "/static/img/logo.png",
            "rel": "icon",
            "sizes": "32x32",
            "type": "image/png",
        },
    ],

    "SHOW_VIEW_ON_SITE": True,
    "SHOW_HISTORY": True,
    "SHOW_BACK_BUTTON": True,
    
    "DASHBOARD_CALLBACK": "core.admin_utils.dashboard_callback",
    
    "COLORS": {
        "primary": {
            "50": "#f0fdf4",
            "100": "#dcfce7",
            "500": "#22c55e",
            "600": "#16a34a",
            "900": "#14532d",
        }
    },

     "SIDEBAR": {
        "show_search": True,
        "show_all_applications": False,  # only show the curated groups below
        "navigation": [
            {
                "title": _("Tenant Management"),
                "separator": True,
                "collapsible": True,
                "permission": "core.admin_utils.is_public_schema",
                "items": [
                    {
                        "title": _("Schools"),
                        "icon": "school",
                        "link": reverse_lazy("admin:core_school_changelist"),
                    },
                    {
                        "title": _("School Modules"),
                        "icon": "extension",
                        "link": reverse_lazy("admin:core_schoolmodule_changelist"),
                    },
                    {
                        "title": _("Domains"),
                        "icon": "dns",
                        "link": reverse_lazy("admin:core_domain_changelist"),
                    },
                    {
                        "title": _("Users"),
                        "icon": "manage_accounts",
                        "link": reverse_lazy("admin:core_user_changelist"),
                    },
                ],
            },
            {
                "title": _("Academics"),
                "separator": True,
                "collapsible": True,
                "permission": "core.admin_utils.is_tenant_schema",
                "items": [
                    {
                        "title": _("Academic Years"),
                        "icon": "event",
                        "link": reverse_lazy("admin:core_academicyear_changelist"),
                    },
                    {
                        "title": _("Courses"),
                        "icon": "menu_book",
                        "link": reverse_lazy("admin:core_course_changelist"),
                    },
                    {
                        "title": _("Batches"),
                        "icon": "groups",
                        "link": reverse_lazy("admin:core_batch_changelist"),
                    },
                    {
                        "title": _("Subjects"),
                        "icon": "book",
                        "link": reverse_lazy("admin:core_subject_changelist"),
                    },
                    {
                        "title": _("Students"),
                        "icon": "person",
                        "link": reverse_lazy("admin:core_student_changelist"),
                    },
                    {
                        "title": _("Guardians"),
                        "icon": "family_restroom",
                        "link": reverse_lazy("admin:core_guardian_changelist"),
                    },
                    {
                        "title": _("Employees"),
                        "icon": "badge",
                        "link": reverse_lazy("admin:core_employee_changelist"),
                    },
                    {
                        "title": _("Exam Groups"),
                        "icon": "quiz",
                        "link": reverse_lazy("admin:core_examgroup_changelist"),
                    },
                    {
                        "title": _("Exams"),
                        "icon": "assignment",
                        "link": reverse_lazy("admin:core_exam_changelist"),
                    },
                    {
                        "title": _("Grading Scales"),
                        "icon": "grade",
                        "link": reverse_lazy("admin:core_gradingscale_changelist"),
                    },
                    {
                        "title": _("Attendance"),
                        "icon": "checklist",
                        "link": reverse_lazy("admin:core_attendance_changelist"),
                    },
                    {
                        "title": _("Report Templates"),
                        "icon": "description",
                        "link": reverse_lazy("admin:core_reporttemplate_changelist"),
                    },
                ],
            },
            {
                "title": _("Finance"),
                "separator": True,
                "collapsible": True,
                "permission": "core.admin_utils.is_tenant_schema",
                "items": [
                    {
                        "title": _("Transaction Categories"),
                        "icon": "category",
                        "link": reverse_lazy("admin:core_financetransactioncategory_changelist"),
                    },
                    {
                        "title": _("Transactions"),
                        "icon": "receipt_long",
                        "link": reverse_lazy("admin:core_financetransaction_changelist"),
                    },
                    {
                        "title": _("Fee Categories"),
                        "icon": "sell",
                        "link": reverse_lazy("admin:core_feecategory_changelist"),
                    },
                    {
                        "title": _("Fee Collections"),
                        "icon": "collections_bookmark",
                        "link": reverse_lazy("admin:core_feecollection_changelist"),
                    },
                    {
                        "title": _("Student Fees"),
                        "icon": "account_balance_wallet",
                        "link": reverse_lazy("admin:core_financefee_changelist"),
                    },
                    {
                        "title": _("Fee Discounts"),
                        "icon": "percent",
                        "link": reverse_lazy("admin:core_feediscount_changelist"),
                    },
                    {
                        "title": _("Fine Slabs"),
                        "icon": "warning",
                        "link": reverse_lazy("admin:core_fineslab_changelist"),
                    },
                    {
                        "title": _("Fee Transactions"),
                        "icon": "payments",
                        "link": reverse_lazy("admin:core_feetransaction_changelist"),
                    },
                    {
                        "title": _("Family Invoices"),
                        "icon": "receipt",
                        "link": reverse_lazy("admin:core_familyinvoice_changelist"),
                    },
                ],
            },
        ],
    },
}