from config.settings import *


class DisableMigrations:
    def __contains__(self, item):
        return True

    def __getitem__(self, item):
        return None


MIGRATION_MODULES = DisableMigrations()

PASSWORD_HASHERS = [
    "django.contrib.auth.hashers.MD5PasswordHasher",
]

EMAIL_BACKEND = "django.core.mail.backends.locmem.EmailBackend"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": True,
}

TESTING = True

# Never reach out to QuickBooks (or any external service) during tests. The
# Student post_save signal otherwise tries to refresh an OAuth token, which
# does a DNS lookup that hangs until the pytest-timeout fires.
QUICKBOOKS_AUTO_SYNC_ENABLED = False

# Use in-process caching/sessions so tests never connect to Redis. Production
# routes sessions through the cache backend (SESSION_ENGINE=cache → Redis); a
# Django test-client force_login otherwise blocks on a Redis connect until the
# pytest-timeout fires.
CACHES = {
    "default": {
        "BACKEND": "django.core.cache.backends.locmem.LocMemCache",
    }
}
SESSION_ENGINE = "django.contrib.sessions.backends.cache"
SESSION_CACHE_ALIAS = "default"

# Tests render full pages (e.g. via Django's test Client) without ever running
# collectstatic, so the manifest-based storage used outside DEBUG would raise
# "Missing staticfiles manifest entry" for every {% static %} tag. Fall back to
# the plain filesystem storage, which resolves paths directly.
STORAGES = {
    **STORAGES,
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}