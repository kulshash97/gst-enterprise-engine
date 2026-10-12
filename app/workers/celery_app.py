from celery import Celery
from app.core.config import get_settings

settings = get_settings()

celery_app = Celery(
    "apextax_worker",
    broker=str(settings.REDIS_URL),
    backend=str(settings.REDIS_URL)
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Kolkata",
    enable_utc=True,
)
