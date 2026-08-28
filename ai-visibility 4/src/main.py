from datetime import datetime, timedelta
from fastapi import FastAPI, Depends
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session
from apscheduler.schedulers.background import BackgroundScheduler

from .db import get_db, init_db
from .models import Brand, TrackedQuery, Snapshot
from .scheduler import run_query_once

# NOTE: this process serves the API only. Scheduled polling runs in
# worker.py as a separate process/container — see that file and
# CLAUDE.md's "Split the scheduler from the web process" note. We still
# need a scheduler handle here so newly created queries can register their
# first job immediately (see create_query below), but this instance never
# runs schedule_all_active_queries() itself.
app = FastAPI(title="AI Visibility Tracker")
scheduler = BackgroundScheduler()


@app.on_event("startup")
def on_startup():
    init_db()
    scheduler.start()


@app.get("/health")
def health():
    return {"status": "ok"}


@app.get("/dashboard")
def dashboard(): return FileResponse("src/static/dashboard.html")


# ---------- request/response schemas ----------

class BrandIn(BaseModel):
    name: str
    aliases: list[str] = []


class TrackedQueryIn(BaseModel):
    brand_id: int
    query_text: str
    surfaces: list[str]  # e.g. ["chatgpt", "gemini", "google_ai_overview"]
    poll_interval_minutes: int = 1440


# ---------- brand + query management ----------

@app.post("/brands")
def create_brand(payload: BrandIn, db: Session = Depends(get_db)):
    brand = Brand(name=payload.name, aliases=payload.aliases)
    db.add(brand)
    db.commit()
    db.refresh(brand)
    return {"id": brand.id, "name": brand.name, "aliases": brand.aliases}


@app.post("/queries")
def create_query(payload: TrackedQueryIn, db: Session = Depends(get_db)):
    tq = TrackedQuery(
        brand_id=payload.brand_id,
        query_text=payload.query_text,
        surfaces=payload.surfaces,
        poll_interval_minutes=payload.poll_interval_minutes,
    )
    db.add(tq)
    db.commit()
    db.refresh(tq)

    # Kick off one immediate check so the user sees data right away. The
    # recurring schedule itself is owned by worker.py, which reconciles
    # against active TrackedQuery rows on its own interval (see
    # scheduler.py::schedule_all_active_queries) — this process doesn't
    # register recurring jobs to avoid duplicate polling if the web
    # service is ever scaled to multiple instances.
    scheduler.add_job(run_query_once, args=[tq.id])

    return {"id": tq.id, "query_text": tq.query_text, "surfaces": tq.surfaces}



# ---------- list endpoints (for the dashboard) ----------

@app.get("/brands")
def list_brands(db: Session = Depends(get_db)):
        brands = db.query(Brand).order_by(Brand.id).all()
        return [{"id": b.id, "name": b.name, "aliases": b.aliases} for b in brands]


def _query_summary(q):
        latest = {}
        for s in sorted(q.snapshots, key=lambda x: x.checked_at): latest[s.surface] = {"mentioned": s.mentioned, "prominence": s.prominence, "sentiment": s.sentiment, "snippet": s.snippet, "checked_at": s.checked_at.isoformat()}
           return {"id": q.id, "query_text": q.query_text, "surfaces": q.surfaces, "latest": latest}


@app.get("/brands/{brand_id}/queries")
def list_queries(brand_id: int, db: Session = Depends(get_db)):
        queries = db.query(TrackedQuery).filter_by(brand_id=brand_id).order_by(TrackedQuery.id).all()
        return [_query_summary(q) for q in queries]

# ---------- dashboard data ----------

@app.get("/brands/{brand_id}/visibility")
def get_visibility(brand_id: int, days: int = 30, surface: str | None = None, db: Session = Depends(get_db)):
    """
    Returns per-day mention rate and average prominence for a brand, optionally
    filtered to one surface, for charting on a dashboard.
    """
    since = datetime.utcnow() - timedelta(days=days)

    q = (
        db.query(Snapshot)
        .join(TrackedQuery)
        .filter(TrackedQuery.brand_id == brand_id, Snapshot.checked_at >= since)
    )
    if surface:
        q = q.filter(Snapshot.surface == surface)

    snapshots = q.order_by(Snapshot.checked_at).all()

    by_day: dict[str, list[Snapshot]] = {}
    for s in snapshots:
        day = s.checked_at.strftime("%Y-%m-%d")
        by_day.setdefault(day, []).append(s)

    series = []
    for day, rows in sorted(by_day.items()):
        mention_rate = sum(1 for r in rows if r.mentioned) / len(rows)
        avg_prominence = sum(r.prominence for r in rows) / len(rows)
        series.append({"date": day, "mention_rate": round(mention_rate, 3), "avg_prominence": round(avg_prominence, 3), "n": len(rows)})

    return {"brand_id": brand_id, "surface": surface or "all", "series": series}


@app.get("/queries/{query_id}/snapshots")
def get_snapshots(query_id: int, limit: int = 50, db: Session = Depends(get_db)):
    rows = (
        db.query(Snapshot)
        .filter_by(query_id=query_id)
        .order_by(Snapshot.checked_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "surface": r.surface,
            "checked_at": r.checked_at.isoformat(),
            "mentioned": r.mentioned,
            "prominence": r.prominence,
            "sentiment": r.sentiment,
            "snippet": r.snippet,
        }
        for r in rows
    ]


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(app, host="0.0.0.0", port=8000)
