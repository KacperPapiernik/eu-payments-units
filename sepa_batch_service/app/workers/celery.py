from celery import Celery
from celery.schedules import crontab

import json
from pathlib import Path

from sepa_batch_service.app.config import settings


CONFIG_PATH = Path("sepa_batch_service/config/batch_schedule.json")


def load_batch_schedule():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def build_beat_schedule():
    config = load_batch_schedule()

    if config["mode"] == "interval":

        interval = config.get("interval_minutes", 5)

        return {
            "close-session-interval": {
                "task": "sepa_batch_service.app.workers.session_closer.periodic_session_close",
                "schedule": interval * 60,
            }
        }

    elif config["mode"] == "fixed_times":

        schedule = {}

        for idx, time_str in enumerate(config.get("times", [])):

            hour, minute = time_str.split(":")

            schedule[f"close-session-{idx}"] = {
                "task": "sepa_batch_service.app.workers.session_closer.periodic_session_close",
                "schedule": crontab(
                    hour=int(hour),
                    minute=int(minute)
                ),
            }

        return schedule

    return {}


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
    beat_schedule=build_beat_schedule(),
)