from datetime import datetime
from sqlalchemy import String, Integer, Float, Boolean, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import Mapped, mapped_column, relationship
from .db import Base


class Brand(Base):
    __tablename__ = "brands"

    id: Mapped[int] = mapped_column(primary_key=True)
    name: Mapped[str] = mapped_column(String(200))
    # Alternate names/spellings the detector should also treat as a match
    aliases: Mapped[list] = mapped_column(JSON, default=list)

    queries: Mapped[list["TrackedQuery"]] = relationship(back_populates="brand")


class TrackedQuery(Base):
    __tablename__ = "tracked_queries"

    id: Mapped[int] = mapped_column(primary_key=True)
    brand_id: Mapped[int] = mapped_column(ForeignKey("brands.id"))
    query_text: Mapped[str] = mapped_column(String(500))
    # Which provider keys (e.g. "chatgpt", "gemini", "google_ai_overview") to poll
    surfaces: Mapped[list] = mapped_column(JSON, default=list)
    poll_interval_minutes: Mapped[int] = mapped_column(Integer, default=1440)
    active: Mapped[bool] = mapped_column(Boolean, default=True)

    brand: Mapped["Brand"] = relationship(back_populates="queries")
    snapshots: Mapped[list["Snapshot"]] = relationship(back_populates="query")


class Snapshot(Base):
    """One provider's answer to one tracked query at one point in time."""

    __tablename__ = "snapshots"

    id: Mapped[int] = mapped_column(primary_key=True)
    query_id: Mapped[int] = mapped_column(ForeignKey("tracked_queries.id"))
    surface: Mapped[str] = mapped_column(String(50))
    checked_at: Mapped[datetime] = mapped_column(DateTime, default=datetime.utcnow)

    mentioned: Mapped[bool] = mapped_column(Boolean, default=False)
    # 1.0 = brand is the headline answer, lower = mentioned in passing / far down
    prominence: Mapped[float] = mapped_column(Float, default=0.0)
    sentiment: Mapped[str] = mapped_column(String(20), default="neutral")  # positive/neutral/negative
    snippet: Mapped[str] = mapped_column(Text, default="")
    raw_response: Mapped[str] = mapped_column(Text, default="")

    query: Mapped["TrackedQuery"] = relationship(back_populates="snapshots")
