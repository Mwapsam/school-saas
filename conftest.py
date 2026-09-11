"""
Pytest configuration for Django tests
This file ensures Django is properly configured before tests run
"""
import os
import django
from django.conf import settings

def pytest_configure():
    """Configure Django settings for pytest"""
    os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')
    
    # Configure Django before any imports
    if not settings.configured:
        django.setup()

    # The test client issues plain-HTTP requests. Production settings enable
    # SECURE_SSL_REDIRECT (because DEBUG is off), which turns every API request
    # into a 301 redirect to https:// and breaks status-code assertions. HTTPS
    # enforcement is a deployment concern the test suite does not exercise, so
    # disable it (and HSTS) for the duration of the test session.
    settings.SECURE_SSL_REDIRECT = False
    settings.SECURE_HSTS_SECONDS = 0

def pytest_sessionstart(session):
    """Called after the Session object has been created"""
    # Ensure Django is fully set up
    if hasattr(django, 'setup'):
        django.setup()


def pytest_collection_modifyitems(config, items):
    """Apply optimizations to reduce schema creation overhead"""
    for item in items:
        # Skip schema creation for URL resolution tests
        if 'test_api_urls' in str(item.fspath):
            # These tests don't need real database
            if hasattr(item, 'add_marker'):
                item.add_marker('django_db')
