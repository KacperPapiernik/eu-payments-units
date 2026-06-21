import logging
from celery import Celery
from celery.schedules import crontab

import json
from pathlib import Path

from sepa_batch_service.app.config import settings

logger = logging.getLogger(__name__)

CONFIG_PATH = Path("sepa_batch_service/config/batch_schedule.json")


def load_batch_schedule():
    with open(CONFIG_PATH, "r") as f:
        return json.load(f)


def build_beat_schedule():
    try:
        config = load_batch_schedule()

        if config["mode"] == "interval":
            interval = config.get("interval_minutes", 5)
            logger.info(f"Building schedule: interval mode, every {interval} min")
            return {
                "close-session-interval": {
                    "task": "sepa_batch_service.app.workers.session_closer.periodic_session_close",
                    "schedule": interval * 60,
                }
            }

        elif config["mode"] == "fixed_times":
            times = config.get("times", [])
            if not times:
                logger.warning("fixed_times mode selected but 'times' list is empty or missing")
                return {}

            schedule = {}
            for idx, time_str in enumerate(times):
                try:
                    hour, minute = time_str.split(":")
                    schedule[f"close-session-{idx}"] = {
                        "task": "sepa_batch_service.app.workers.session_closer.periodic_session_close",
                        "schedule": crontab(
                            hour=int(hour),
                            minute=int(minute)
                        ),
                    }
                except (ValueError, TypeError) as e:
                    logger.error(f"Invalid time format '{time_str}': {e}")

            if not schedule:
                logger.warning("No valid schedule entries created for fixed_times mode")
                return {}

            logger.info(f"Building schedule: fixed_times mode, {len(schedule)} time(s): {times}")
            return schedule

        logger.error(f"Unknown schedule mode: '{config.get('mode')}'")
        return {}

    except Exception as e:
        logger.error(f"Failed to build beat schedule: {e}", exc_info=True)
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