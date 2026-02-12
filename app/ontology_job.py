import os
import time

from app.services.opsgraph_service import OpsGraphService


def run_loop() -> None:
    interval = int(os.getenv("ONTOLOGY_REFRESH_SECONDS", "3600"))
    service = OpsGraphService()
    while True:
        service.build_ontology()
        time.sleep(interval)


if __name__ == "__main__":
    run_loop()
