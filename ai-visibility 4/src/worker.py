"""
Worker process entrypoint. Runs the recurring polling schedule only — no
HTTP server (see main.py / web.py for that). Deploy this as its own
process/container alongside the web service; see CLAUDE.md and the
deployment steps for why they're split.
"""

import logging
import time

from apscheduler.schedulers.background import BackgroundScheduler

from .db import init_db
from .scheduler import schedule_all_active_queries

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("ai_visibility.worker")

RECONCILE_INTERVAL_MINUTES = 1


def main():
    init_db()
    scheduler = BackgroundScheduler()
    scheduler.start()

    # Register jobs for whatever's active right now...
    schedule_all_active_queries(scheduler)
    logger.info("Worker started, %d job(s) scheduled", len(scheduler.get_jobs()))

    # ...and keep re-syncing periodically so queries created/edited via the
    # API (which runs in a separate process) get picked up automatically.
    scheduler.add_job(
        schedule_all_active_queries,
        "interval",
        minutes=RECONCILE_INTERVAL_MINUTES,
        args=[scheduler],
        id="reconciler",
    )

    try:
        while True:
            time.sleep(60)
    except (KeyboardInterrupt, SystemExit):
        logger.info("Worker shutting down")
        scheduler.shutdown()


if __name__ == "__main__":
    main()
