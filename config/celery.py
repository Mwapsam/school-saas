import os
from celery import Celery
from celery.schedules import crontab

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

app = Celery("config")

app.config_from_object("django.conf:settings", namespace="CELERY")

app.autodiscover_tasks()

app.conf.beat_schedule = {
    'cleanup-old-zip-files': {
        'task': 'core.tasks.cleanup_old_zip_files',
        'schedule': crontab(hour=5, minute=0),  # Daily at 5:00 AM
        'kwargs': {'days_old': 1}  # Clean ZIP files older than 1 day
    },
    'notify-fee-due': {
        'task': 'core.tasks.notify_fee_due',
        'schedule': crontab(hour=6, minute=0),  # Daily at 6:00 AM; self de-dups per 7 days
    },
    'proactive-quickbooks-token-refresh': {
        'task': 'core.tasks.proactive_quickbooks_token_refresh',
        'schedule': crontab(minute='*/15'),  # keep the OAuth token alive
    },
    'quickbooks-token-health-check': {
        'task': 'core.tasks.check_quickbooks_token_health',
        'schedule': crontab(minute=0),  # hourly connection-health summary
    },
    'daily-quickbooks-catchup': {
        'task': 'core.tasks.retry_failed_quickbooks_fee_syncs',
        'schedule': crontab(hour=3, minute=0),  # Daily at 3:00 AM
        'kwargs': {'days_back': 3},
    },
    'hr-generate-tasks': {
        'task': 'core.tasks.hr_generate_tasks',
        'schedule': crontab(hour=4, minute=30),  # Daily at 4:30 AM (per-tenant schema loop)
    },
    # 'cleanup-failed-quickbooks-syncs' stays disabled: the task queries
    # QuickBooksCustomerSync/QuickBooksSyncLog without a per-tenant
    # schema_context, so it must be given a schema loop before it can be
    # scheduled safely.
    # 'cleanup-old-report-files': {
    #     'task': 'core.tasks.cleanup_old_report_files',
    #     'schedule': crontab(hour=4, minute=0),  # Daily at 4:00 AM
    #     'kwargs': {'days_old': 90}  # Clean reports older than 90 days
    # },
}

app.conf.timezone = 'Africa/Lusaka'