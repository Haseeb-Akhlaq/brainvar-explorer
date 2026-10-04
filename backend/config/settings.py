"""
Django settings for the BrainVar Trajectory Explorer API.

Configuration is environment-driven; see .env.example.
"""

import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent.parent
load_dotenv(BASE_DIR / ".env")


def env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def env_list(name: str, default: str = "") -> list[str]:
    return [item.strip() for item in os.environ.get(name, default).split(",") if item.strip()]


# --- Core ------------------------------------------------------------------

# Dev-only fallback: deployments must supply DJANGO_SECRET_KEY.
SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "django-insecure-dev-key-change-me")
DEBUG = env_bool("DJANGO_DEBUG", True)
ALLOWED_HOSTS = env_list("DJANGO_ALLOWED_HOSTS", "localhost,127.0.0.1,[::1]")

INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",  # ArrayField, trigram search
    # Third party
    "rest_framework",
    "drf_spectacular",
    "drf_spectacular_sidecar",  # self-hosted Swagger UI / ReDoc assets
    "corsheaders",
    "auditlog",  # model-change audit trail
    # Local
    "users",
    "brainvar",
    "activity",  # auth + data-access events
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
    # After AuthenticationMiddleware: it reads request.user to attribute each
    # change to an actor, and the remote address for the entry.
    "auditlog.middleware.AuditlogMiddleware",
]

# --- Audit trail -----------------------------------------------------------

# Opt in per model rather than sweeping everything up: the dataset tables are
# read-only reference data, so logging them would only add noise. Registration
# happens in users/apps.py.
AUDITLOG_INCLUDE_ALL_MODELS = False
# Loading fixtures or running a data migration is not a user action.
AUDITLOG_DISABLE_ON_RAW_SAVE = True

# Gene views are the one high-volume event. Repeats by the same user of the
# same gene inside this window collapse into the first entry, so paging back
# and forth through a handful of genes does not fill the table.
ACTIVITY_GENE_VIEW_DEDUPE_SECONDS = int(
    os.environ.get("ACTIVITY_GENE_VIEW_DEDUPE_SECONDS", "300")
)

ROOT_URLCONF = "config.urls"
WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [BASE_DIR / "templates"],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    },
]

# --- Database: PostgreSQL --------------------------------------------------

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        "NAME": os.environ.get("POSTGRES_DB", "brainvar_explorer"),
        "USER": os.environ.get("POSTGRES_USER", "postgres"),
        "PASSWORD": os.environ.get("POSTGRES_PASSWORD", ""),
        "HOST": os.environ.get("POSTGRES_HOST", "localhost"),
        "PORT": os.environ.get("POSTGRES_PORT", "5432"),
    }
}

AUTH_USER_MODEL = "users.User"

AUTH_PASSWORD_VALIDATORS = [
    {"NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator"},
    {"NAME": "django.contrib.auth.password_validation.MinimumLengthValidator"},
    {"NAME": "django.contrib.auth.password_validation.CommonPasswordValidator"},
    {"NAME": "django.contrib.auth.password_validation.NumericPasswordValidator"},
]

# --- I18N / static ---------------------------------------------------------

LANGUAGE_CODE = "en-gb"
TIME_ZONE = "Europe/London"
USE_I18N = True
USE_TZ = True

STATIC_URL = "static/"
STATIC_ROOT = BASE_DIR / "staticfiles"
DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

# --- REST framework --------------------------------------------------------

REST_FRAMEWORK = {
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    # Closed by default. Endpoints that must stay reachable without a
    # session — the health probe and the schema — opt out explicitly.
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
    "DEFAULT_SCHEMA_CLASS": "drf_spectacular.openapi.AutoSchema",
}

# --- OpenAPI schema ---------------------------------------------------------
# Served as an interactive Swagger UI at /api/docs/ and as raw OpenAPI 3 at
# /api/schema/.

SPECTACULAR_SETTINGS = {
    "TITLE": "BrainVar Trajectory Explorer API",
    "DESCRIPTION": (
        "Gene expression across human brain development.\n\n"
        "176 BrainVar RNA-seq samples spanning 6 post-conception weeks to "
        "adulthood, for 60,155 genes. Every endpoint is read-only and "
        "returns JSON.\n\n"
        "Expression is reported as CPM; the application plots "
        "`log2(CPM + 0.001)` against `log2(age_days)`, matching the analysis "
        "script this API replaces. The fitted curve is LOESS "
        "(span 0.75, degree 2) with a 95% confidence band."
    ),
    "VERSION": "1.0.0",
    # The schema endpoint should not document itself.
    "SERVE_INCLUDE_SCHEMA": False,
    "SCHEMA_PATH_PREFIX": "/api/",
    "COMPONENT_SPLIT_REQUEST": True,
    "SORT_OPERATIONS": False,
    # Serve the UI assets from staticfiles rather than a CDN.
    "SWAGGER_UI_DIST": "SIDECAR",
    "SWAGGER_UI_FAVICON_HREF": "SIDECAR",
    "REDOC_DIST": "SIDECAR",
    "SWAGGER_UI_SETTINGS": {
        "deepLinking": True,
        "persistAuthorization": True,
        "displayRequestDuration": True,
        "filter": True,
        "tryItOutEnabled": True,
    },
    "TAGS": [
        {"name": "auth", "description": "Session login, logout and the current user."},
        {"name": "genes", "description": "Search genes and read their expression trajectories."},
        {"name": "dataset", "description": "Counts and ranges describing the loaded dataset."},
        {"name": "health", "description": "Liveness and readiness."},
    ],
}

# --- CORS ------------------------------------------------------------------
# The Vite dev server runs on a different origin to the API.

CORS_ALLOWED_ORIGINS = env_list(
    "CORS_ALLOWED_ORIGINS",
    "http://localhost:5173,http://127.0.0.1:5173",
)
CORS_ALLOW_CREDENTIALS = True
CSRF_TRUSTED_ORIGINS = env_list("CSRF_TRUSTED_ORIGINS", ",".join(CORS_ALLOWED_ORIGINS))

# --- BrainVar data ---------------------------------------------------------
# Where the raw source files live. Mounted read-only at /data in Docker;
# defaults to the repo copy when running on the host.

BRAINVAR_DATA_DIR = Path(
    os.environ.get("BRAINVAR_DATA_DIR", BASE_DIR.parent / "data" / "brainvar")
)

# --- Security (production hardening, off in DEBUG) -------------------------

if not DEBUG:
    SECURE_SSL_REDIRECT = env_bool("SECURE_SSL_REDIRECT", True)
    SESSION_COOKIE_SECURE = True
    CSRF_COOKIE_SECURE = True
    SECURE_HSTS_SECONDS = int(os.environ.get("SECURE_HSTS_SECONDS", 31536000))
    SECURE_HSTS_INCLUDE_SUBDOMAINS = True
    SECURE_HSTS_PRELOAD = True
    SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")
    SECURE_CONTENT_TYPE_NOSNIFF = True

    # The app and the API are served from different subdomains, so the session
    # and CSRF cookies are cross-site. Browsers only send those when SameSite
    # is None, which in turn requires Secure — both set above.
    SESSION_COOKIE_SAMESITE = os.environ.get("SESSION_COOKIE_SAMESITE", "None")
    CSRF_COOKIE_SAMESITE = os.environ.get("CSRF_COOKIE_SAMESITE", "None")
    # Shared parent domain so one cookie works across brainvar.* and api.brainvar.*
    SESSION_COOKIE_DOMAIN = os.environ.get("SESSION_COOKIE_DOMAIN") or None
    CSRF_COOKIE_DOMAIN = os.environ.get("CSRF_COOKIE_DOMAIN") or None

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "verbose": {"format": "{levelname} {asctime} {name} {message}", "style": "{"},
    },
    "handlers": {
        "console": {"class": "logging.StreamHandler", "formatter": "verbose"},
    },
    "root": {"handlers": ["console"], "level": os.environ.get("LOG_LEVEL", "INFO")},
}


# --- Email -------------------------------------------------------------------
#
# Used for the account invitation the admin panel sends. Credentials come from
# the environment and never from source: EMAIL_HOST_PASSWORD is a Gmail app
# password, and backend/.env is gitignored.
#
# With no host user configured the console backend is selected instead, so a
# checkout with no secrets still runs and prints invitations to the log rather
# than failing. Django's test runner overrides this with the locmem backend, so
# tests never open a socket.
EMAIL_HOST = os.environ.get("EMAIL_HOST", "smtp.gmail.com")
EMAIL_PORT = int(os.environ.get("EMAIL_PORT", 587))
EMAIL_USE_TLS = env_bool("EMAIL_USE_TLS", True)
EMAIL_HOST_USER = os.environ.get("EMAIL_HOST_USER", "")
EMAIL_HOST_PASSWORD = os.environ.get("EMAIL_HOST_PASSWORD", "")
EMAIL_BACKEND = os.environ.get(
    "EMAIL_BACKEND",
    "django.core.mail.backends.smtp.EmailBackend"
    if EMAIL_HOST_USER
    else "django.core.mail.backends.console.EmailBackend",
)
# Bounded so a dead SMTP host cannot hold an admin's request open indefinitely.
EMAIL_TIMEOUT = int(os.environ.get("EMAIL_TIMEOUT", 15))

EMAIL_FROM_NAME = os.environ.get("EMAIL_FROM_NAME", "BrainVar Trajectory Explorer")
EMAIL_FROM_ADDRESS = os.environ.get("EMAIL_FROM_ADDRESS", EMAIL_HOST_USER)
DEFAULT_FROM_EMAIL = (
    f'"{EMAIL_FROM_NAME}" <{EMAIL_FROM_ADDRESS}>' if EMAIL_FROM_NAME else EMAIL_FROM_ADDRESS
)
EMAIL_SUPPORT_ADDRESS = os.environ.get("EMAIL_SUPPORT_ADDRESS", EMAIL_FROM_ADDRESS)

# Where the invitation tells the recipient to sign in. The app, not the API.
APP_LOGIN_URL = os.environ.get("APP_LOGIN_URL", "http://localhost:5173/login")

# Attached to the invitation and referenced by Content-ID, so it renders
# without a network fetch — most mail clients block remote images by default.
EMAIL_LOGO_PATH = Path(
    os.environ.get("EMAIL_LOGO_PATH", BASE_DIR / "users" / "email_assets" / "brainvar-logo.png")
)
