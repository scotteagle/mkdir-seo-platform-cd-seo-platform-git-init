import asyncio
import logging
from apscheduler.schedulers.background import BackgroundScheduler

from .db import SessionLocal
from .models import TrackedQuery, Snapshot
from .providers import PROVIDERS
from .detector import analyze_mention

logger = logging.getLogger("ai_visibility.scheduler")


def run_query_once(query_id: int):
    """Poll every configured surface for one tracked query and store snapshots."""
    db = SessionLocal()
    try:
        tq = db.get(TrackedQuery, query_id)
        if not tq or not tq.active:
            return

        for surface_key in tq.surfaces:
            provider = PROVIDERS.get(surface_key)
            if not provider:
                logger.warning("Unknown surface %s on query %s", surface_key, query_id)
                continue

            try:
                response_text = asyncio.run(provider.query(tq.query_text))
            except Exception as exc:  # provider outage shouldn't kill the whole job
                logger.error("Provider %s failed for query %s: %s", surface_key, query_id, exc)
                continue

            analysis = analyze_mention(tq.brand.name, tq.brand.aliases, response_text)

            snapshot = Snapshot(
                query_id=tq.id,
                surface=surface_key,
                mentioned=analysis["mentioned"],
                prominence=analysis["prominence"],
                sentiment=analysis["sentiment"],
                snippet=analysis["snippet"],
                raw_response=response_text or "",
            )
            db.add(snapshot)

        db.commit()
    finally:
        db.close()


def schedule_all_active_queries(scheduler: BackgroundScheduler):
    """
    (Re)register a recurring job per active tracked query, and remove jobs
    for queries that were deactivated. `add_job(..., replace_existing=True)`
    is idempotent, so this is safe to call repeatedly — the worker calls it
    once on startup and then on a recurring 'reconciler' job so new queries
    created via the API (see main.py::create_query) get picked up without a
    worker restart.
    """
    db = SessionLocal()
    try:
        active_ids = set()
        for tq in db.query(TrackedQuery).filter_by(active=True).all():
            job_id = f"query_{tq.id}"
            active_ids.add(job_id)
            scheduler.add_job(
                run_query_once,
                "interval",
                minutes=tq.poll_interval_minutes,
                args=[tq.id],
                id=job_id,
                replace_existing=True,
            )

        for job in scheduler.get_jobs():
            if job.id.startswith("query_") and job.id not in active_ids:
                scheduler.remove_job(job.id)
    finally:
        db.close()
