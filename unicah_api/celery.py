from __future__ import absolute_import, unicode_literals
import os
from celery.schedules import crontab
from celery import Celery

# set the default Django settings module for the 'celery' program.
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'unicah_api.settings')

app = Celery('unicah_api',
			 include=['unicah_api.tasks'])

# Using a string here means the worker don't have to serialize
# the configuration object to child processes.
# - namespace='CELERY' means all celery-related configuration keys
#   should have a `CELERY_` prefix.
app.config_from_object('django.conf:settings', namespace='CELERY')

# Load task modules from all registered Django app configs.
app.autodiscover_tasks()

@app.task(bind=True)
def debug_task(self):
  print('Request: {0!r}'.format(self.request))

app.conf.update(
    worker_max_tasks_per_child=1,
    broker_pool_limit=None
)

app.conf.beat_schedule = {
    'add-every-minute-contrab': {
        'task': 'poll_grade_changes',
        'schedule': crontab(),
        'args': (16, 16),
    }
}