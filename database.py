"""Aircraft reference data — a small shared store with live verification status.

Deliberately minimal: no auth, no locking. One table of aircraft; edits and
sign-offs are write-through and immediately visible to everyone. Sign-offs
record typed initials (no accounts, by design).
"""
import json
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (Boolean, Column, DateTime, Float, Integer, String,
                        Text, select, text)
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine
from sqlalchemy.orm import declarative_base

from config import DATABASE_URL

engine = create_async_engine(DATABASE_URL, echo=False)
SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
Base = declarative_base()

DIM_FIELDS = ["LENGTH", "WINGSPAN", "NOSE_TO_WING", "NOSE_HEIGHT",
              "TAIL_HEIGHT", "WING_HEIGHT"]


def utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


class Aircraft(Base):
    __tablename__ = "aircraft"
    id = Column(Integer, primary_key=True)
    ac_type = Column(String(12), unique=True, nullable=False, index=True)
    length = Column(Float)
    wingspan = Column(Float)
    nose_to_wing = Column(Float)
    nose_height = Column(Float)
    tail_height = Column(Float)
    wing_height = Column(Float)
    source = Column(Text, nullable=False, default="")
    verified = Column(Boolean, nullable=False, server_default=text("FALSE"))
    checked_by = Column(String(16), nullable=False, default="")
    checked_date = Column(String(24), nullable=False, default="")
    updated_at = Column(DateTime, nullable=False, default=utcnow)
    updated_by = Column(String(16), nullable=False, default="")


class ChangeLog(Base):
    __tablename__ = "change_log"
    id = Column(Integer, primary_key=True)
    at = Column(DateTime, nullable=False, default=utcnow, index=True)
    who = Column(String(16), nullable=False, default="")
    action = Column(String(24), nullable=False)
    ac_type = Column(String(12), nullable=False, default="", index=True)
    detail = Column(Text, nullable=False, default="")


def to_json(a: Aircraft) -> dict:
    return {
        "AC_TYPE": a.ac_type,
        "LENGTH": a.length, "WINGSPAN": a.wingspan, "NOSE_TO_WING": a.nose_to_wing,
        "NOSE_HEIGHT": a.nose_height, "TAIL_HEIGHT": a.tail_height, "WING_HEIGHT": a.wing_height,
        "SOURCE": a.source or "",
        "VERIFIED": "YES" if a.verified else "NO",
        "CHECKED_BY": a.checked_by or "", "CHECKED_DATE": a.checked_date or "",
        "updated_at": a.updated_at.isoformat() + "Z", "updated_by": a.updated_by or "",
    }


async def init_db():
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    # Seed once from the packaged master list if the table is empty.
    async with SessionLocal() as db:
        n = (await db.execute(select(Aircraft))).first()
        if n is None:
            seed = Path(__file__).parent / "seed_aircraft.json"
            if seed.exists():
                for r in json.loads(seed.read_text()):
                    db.add(Aircraft(
                        ac_type=r["AC_TYPE"], length=r.get("LENGTH"), wingspan=r.get("WINGSPAN"),
                        nose_to_wing=r.get("NOSE_TO_WING"), nose_height=r.get("NOSE_HEIGHT"),
                        tail_height=r.get("TAIL_HEIGHT"), wing_height=r.get("WING_HEIGHT"),
                        source=r.get("SOURCE", ""),
                        verified=str(r.get("VERIFIED", "NO")).upper() == "YES",
                        checked_by=r.get("CHECKED_BY", ""), checked_date=r.get("CHECKED_DATE", ""),
                        updated_by="seed"))
                await db.commit()
