"""
Django settings for the Compliance Assistant.

All production-sensitive and model/retrieval configuration is read from the
environment (optionally via a local ``.env`` file). See ``.env.example`` for
the full configuration contract.
"""
import os
import sys
from pathlib import Path

from django.core.exceptions import ImproperlyConfigured
from dotenv import load_dotenv

# Build paths inside the project like this: BASE_DIR / 'subdir'.
BASE_DIR = Path(__file__).resolve().parent.parent

# Load environment variables from .env file (never overrides real env vars).
load_dotenv(BASE_DIR / '.env')

TESTING = len(sys.argv) > 1 and sys.argv[1] == 'test'


def env_bool(name: str, default: bool = False) -> bool:
    value = os.getenv(name)
    if value is None or value.strip() == '':
        return default
    return value.strip().lower() in ('true', '1', 't', 'yes', 'y', 'on')


def env_int(name: str, default: int) -> int:
    value = os.getenv(name)
    if value is None or value.strip() == '':
        return default
    try:
        return int(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f'{name} must be an integer, got {value!r}') from exc


def env_float(name: str, default: float) -> float:
    value = os.getenv(name)
    if value is None or value.strip() == '':
        return default
    try:
        return float(value)
    except ValueError as exc:
        raise ImproperlyConfigured(f'{name} must be a number, got {value!r}') from exc


def env_list(name: str, default: str = '') -> list[str]:
    raw = os.getenv(name, default) or ''
    return [item.strip() for item in raw.split(',') if item.strip()]


# ---------------------------------------------------------------------------
# Core security
# ---------------------------------------------------------------------------

# SECURITY WARNING: don't run with debug turned on in production!
DEBUG = env_bool('DEBUG', False)

_DEV_SECRET = 'django-insecure-local-development-only-key-do-not-use-in-production'
SECRET_KEY = os.getenv('DJANGO_SECRET_KEY', '').strip()
if not SECRET_KEY or SECRET_KEY in ('replace-me', 'change-me-to-a-random-string'):
    if DEBUG or TESTING:
        SECRET_KEY = _DEV_SECRET
    else:
        raise ImproperlyConfigured(
            'DJANGO_SECRET_KEY must be set to a strong random value when DEBUG=False.'
        )

ALLOWED_HOSTS = env_list('ALLOWED_HOSTS', 'localhost,127.0.0.1' if (DEBUG or TESTING) else '')
if TESTING and 'testserver' not in ALLOWED_HOSTS:
    ALLOWED_HOSTS.append('testserver')
CSRF_TRUSTED_ORIGINS = env_list('CSRF_TRUSTED_ORIGINS', '')

SECURE_SSL_REDIRECT = env_bool('DJANGO_SECURE_SSL_REDIRECT', not (DEBUG or TESTING))
_secure_cookies = env_bool('DJANGO_SECURE_COOKIES', not (DEBUG or TESTING))
SESSION_COOKIE_SECURE = _secure_cookies
CSRF_COOKIE_SECURE = _secure_cookies
SESSION_COOKIE_HTTPONLY = True
SECURE_HSTS_SECONDS = env_int('DJANGO_HSTS_SECONDS', 0)
SECURE_HSTS_INCLUDE_SUBDOMAINS = env_bool('DJANGO_HSTS_INCLUDE_SUBDOMAINS', SECURE_HSTS_SECONDS > 0)
SECURE_HSTS_PRELOAD = env_bool('DJANGO_HSTS_PRELOAD', False)
SECURE_CONTENT_TYPE_NOSNIFF = True
SECURE_REFERRER_POLICY = 'same-origin'
X_FRAME_OPTIONS = 'DENY'
if env_bool('DJANGO_TRUST_PROXY_SSL_HEADER', False):
    SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')


# ---------------------------------------------------------------------------
# Application definition
# ---------------------------------------------------------------------------

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',

    # Local apps
    'qa',
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

ROOT_URLCONF = 'compliance_assistant.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [BASE_DIR / 'templates'],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.debug',
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
                'qa.context_processors.roles',
            ],
        },
    },
]

WSGI_APPLICATION = 'compliance_assistant.wsgi.application'


# Database
DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',
    }
}


# Password validation
AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]


# Internationalization
LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True


# Static and media files
STATIC_URL = '/static/'
STATICFILES_DIRS = [BASE_DIR / 'static']
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL = '/media/'
MEDIA_ROOT = Path(os.getenv('MEDIA_ROOT', str(BASE_DIR / 'media')))

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Auth settings
LOGIN_URL = '/login/'
LOGIN_REDIRECT_URL = '/'
LOGOUT_REDIRECT_URL = '/login/'


# ---------------------------------------------------------------------------
# Upload limits
# ---------------------------------------------------------------------------
MAX_UPLOAD_MB = env_int('MAX_UPLOAD_MB', 25)
MAX_PDF_PAGES = env_int('MAX_PDF_PAGES', 500)
# Django buffers uploads larger than this to disk; the form enforces MAX_UPLOAD_MB.
FILE_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024
DATA_UPLOAD_MAX_MEMORY_SIZE = 5 * 1024 * 1024


# ---------------------------------------------------------------------------
# RAG / Compliance Assistant settings
# ---------------------------------------------------------------------------
VECTORSTORE_DIR = Path(os.getenv('VECTORSTORE_DIR', str(BASE_DIR / 'vectorstore')))

# OPENAI_API_KEY is retained as a fallback for existing local .env files.
OPENROUTER_API_KEY = os.getenv('OPENROUTER_API_KEY') or os.getenv('OPENAI_API_KEY', '')
OPENROUTER_BASE_URL = os.getenv('OPENROUTER_BASE_URL', 'https://openrouter.ai/api/v1')
OPENROUTER_MODEL = os.getenv('OPENROUTER_MODEL', '') or 'liquid/lfm-2.5-2.6b:free'
OPENROUTER_JUDGE_MODEL = os.getenv('OPENROUTER_JUDGE_MODEL', '') or OPENROUTER_MODEL
OPENROUTER_FALLBACK_MODELS = env_list('OPENROUTER_FALLBACK_MODELS', '')
LLM_TIMEOUT_SECONDS = env_float('LLM_TIMEOUT_SECONDS', 60.0)
LLM_MAX_OUTPUT_TOKENS = env_int('LLM_MAX_OUTPUT_TOKENS', 1200)
# Optional pricing (USD per 1M tokens) used for cost estimates; 0 for free models.
LLM_INPUT_COST_PER_MTOK = env_float('LLM_INPUT_COST_PER_MTOK', 0.0)
LLM_OUTPUT_COST_PER_MTOK = env_float('LLM_OUTPUT_COST_PER_MTOK', 0.0)

EMBEDDING_MODEL = os.getenv('EMBEDDING_MODEL', 'all-MiniLM-L6-v2')
EMBEDDING_DIMENSION = env_int('EMBEDDING_DIMENSION', 384)
RERANKER_MODEL = os.getenv('RERANKER_MODEL', 'cross-encoder/ms-marco-MiniLM-L-6-v2')

RAG_RETRIEVAL_MODE = os.getenv('RAG_RETRIEVAL_MODE', 'dense')  # baseline until Phase 0 review gate passes
RAG_DENSE_CANDIDATES = env_int('RAG_DENSE_CANDIDATES', 20)
RAG_BM25_CANDIDATES = env_int('RAG_BM25_CANDIDATES', 20)
RAG_RERANK_CANDIDATES = env_int('RAG_RERANK_CANDIDATES', 30)
RAG_TOP_K = env_int('RAG_TOP_K', 5)
RAG_RRF_K = env_int('RAG_RRF_K', 60)
RAG_RERANK_MIN_SCORE = env_float('RAG_RERANK_MIN_SCORE', 0.0)
RAG_DENSE_WEIGHT = env_float('RAG_DENSE_WEIGHT', 1.0)
RAG_BM25_WEIGHT = env_float('RAG_BM25_WEIGHT', 1.0)
RAG_CONFIDENCE_THRESHOLD = env_float('RAG_CONFIDENCE_THRESHOLD', 0.3)  # dense cosine floor
RAG_MAX_AGENT_STEPS = env_int('RAG_MAX_AGENT_STEPS', 6)
RAG_MAX_AGENT_SUBQUESTIONS = env_int('RAG_MAX_AGENT_SUBQUESTIONS', 4)
RAG_AGENT_STEP_TIMEOUT_SECONDS = env_float('RAG_AGENT_STEP_TIMEOUT_SECONDS', 60.0)
RAG_AGENT_TOTAL_TIMEOUT_SECONDS = env_float('RAG_AGENT_TOTAL_TIMEOUT_SECONDS', 240.0)
MAX_QUESTION_CHARS = env_int('MAX_QUESTION_CHARS', 2000)


# ---------------------------------------------------------------------------
# Logging: never log API keys, document content or session data.
# ---------------------------------------------------------------------------
LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'simple': {'format': '%(asctime)s %(levelname)s %(name)s: %(message)s'},
    },
    'handlers': {
        'console': {'class': 'logging.StreamHandler', 'formatter': 'simple'},
    },
    'loggers': {
        'qa': {'handlers': ['console'], 'level': os.getenv('APP_LOG_LEVEL', 'INFO')},
        'rag': {'handlers': ['console'], 'level': os.getenv('APP_LOG_LEVEL', 'INFO')},
        'httpx': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
        'openai': {'handlers': ['console'], 'level': 'WARNING', 'propagate': False},
    },
}
