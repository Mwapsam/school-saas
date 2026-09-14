from django.apps import AppConfig
from django.core import checks


class CoreConfig(AppConfig):
    default_auto_field = 'django.db.models.BigAutoField'
    name = 'core'

    def ready(self):
        """Import signals when the app is ready"""
        import core.signals  # noqa
        self.register_checks()

    def register_checks(self):
        """Register system checks for module URL mapping drift."""
        @checks.register(checks.Tags.models)
        def check_module_url_coverage(app_configs, **kwargs):
            from core.module_urls import find_unmapped_module_urls, validate_module_urls
            errors = []

            try:
                validate_module_urls()
            except ValueError as e:
                errors.append(
                    checks.Error(
                        f"Module URL validation failed: {str(e)}",
                        hint="Check core/module_urls.py URL_MODULE_MAP for invalid module keys.",
                        id="core.E001",
                    )
                )

            unmapped = find_unmapped_module_urls()
            if unmapped:
                errors.append(
                    checks.Warning(
                        f"Found {len(unmapped)} module URL(s) not in URL_MODULE_MAP: {sorted(unmapped)}",
                        hint="Add these URL names to core/module_urls.py URL_MODULE_MAP with their corresponding module keys.",
                        id="core.W001",
                    )
                )

            return errors
