from celery import Celery
from sepa_batch_service.app.config import settings

celery_app = Celery(
    "sepa_batch",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["sepa_batch_service.app.workers.session_closer"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "close-session-every-5-minutes": {
            "task": "sepa_batch_service.app.workers.session_closer.periodic_session_close",
            "schedule": settings.session_close_interval,
        },
    },
)
