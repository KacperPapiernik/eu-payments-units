from celery import Celery
from sepa_instant_service.app.config import settings

celery_app = Celery(
    "sepa_instant",
    broker=settings.redis_url,
    backend=settings.redis_url,
    include=["sepa_instant_service.app.workers.gridlock_worker"]
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    beat_schedule={
        "resolve-pending-every-minute": {
            "task": "sepa_instant_service.app.workers.gridlock_worker.gridlock_resolution",
            "schedule": 60.0,
        },
        "check-alerts-every-minute": {
            "task": "sepa_instant_service.app.workers.gridlock_worker.liquidity_monitoring",
            "schedule": 60.0,
        },
    },
)
