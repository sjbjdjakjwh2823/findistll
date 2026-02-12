import asyncio
import logging
import os

from app.services.event_ingestion_service import EventIngestionService
from app.core.logging import configure_logging

logger = logging.getLogger(__name__)


async def main() -> None:
    if os.getenv("EVENT_INGEST_ENABLED", "0") != "1":
        raise RuntimeError("Event ingestion disabled: set EVENT_INGEST_ENABLED=1")
    svc = EventIngestionService()
    await svc.run_forever()


if __name__ == "__main__":
    configure_logging("event_worker")
    asyncio.run(main())
