"""Aircraft reference-data API.

Open by design (no auth): the data is non-sensitive and the team wants
frictionless access. Sign-offs record typed initials. All writes are
write-through and immediately visible to every client, with a change log.
"""
from contextlib import asynccontextmanager

from fastapi import Depends, FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
from sqlalchemy import select

from config import CORS_ORIGINS
from database import (Aircraft, ChangeLog, DIM_FIELDS, SessionLocal, init_db,
                      to_json, utcnow)


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    yield


app = FastAPI(title="IFP Aircraft Data", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[o.strip() for o in CORS_ORIGINS.split(",")] if CORS_ORIGINS != "*" else ["*"],
    allow_methods=["*"], allow_headers=["*"],
)


async def get_db():
    async with SessionLocal() as db:
        yield db


# ---- schemas ----
class AircraftIn(BaseModel):
    AC_TYPE: str = Field(min_length=2, max_length=12)
    LENGTH: float | None = None
    WINGSPAN: float | None = None
    NOSE_TO_WING: float | None = None
    NOSE_HEIGHT: float | None = None
    TAIL_HEIGHT: float | None = None
    WING_HEIGHT: float | None = None
    SOURCE: str = ""
    who: str = ""            # initials of the editor


class VerifyIn(BaseModel):
    who: str = Field(min_length=1, max_length=16)


DIM_MAP = {"LENGTH": "length", "WINGSPAN": "wingspan", "NOSE_TO_WING": "nose_to_wing",
           "NOSE_HEIGHT": "nose_height", "TAIL_HEIGHT": "tail_height", "WING_HEIGHT": "wing_height"}


async def _log(db, who, action, ac_type, detail=""):
    db.add(ChangeLog(who=(who or "?")[:16], action=action, ac_type=ac_type, detail=detail[:500]))


async def _get(db, ac_type) -> Aircraft:
    a = (await db.execute(select(Aircraft).where(
        Aircraft.ac_type == ac_type.upper()))).scalar_one_or_none()
    if not a:
        raise HTTPException(404, f"{ac_type} not found")
    return a


@app.get("/api/aircraft")
async def list_aircraft(db=Depends(get_db)):
    rows = (await db.execute(select(Aircraft).order_by(Aircraft.ac_type))).scalars().all()
    return {"aircraft": [to_json(a) for a in rows]}


@app.put("/api/aircraft/{ac_type}")
async def upsert_aircraft(ac_type: str, body: AircraftIn, db=Depends(get_db)):
    """Create or update an aircraft's dimensions. Editing any dimension of a
    verified aircraft clears its sign-off (must be re-checked)."""
    ac_type = ac_type.upper()
    a = (await db.execute(select(Aircraft).where(Aircraft.ac_type == ac_type))).scalar_one_or_none()
    new = a is None
    if new:
        a = Aircraft(ac_type=ac_type)
        db.add(a)
    dims_changed = False
    for jsonf, col in DIM_MAP.items():
        val = getattr(body, jsonf)
        if val is not None and getattr(a, col) != val:
            setattr(a, col, val)
            dims_changed = True
    if body.SOURCE:
        a.source = body.SOURCE
    if dims_changed and a.verified:
        a.verified = False
        a.checked_by = ""
        a.checked_date = ""
        await _log(db, body.who, "signoff_cleared", ac_type, "dimension edited")
    a.updated_at = utcnow()
    a.updated_by = (body.who or "?")[:16]
    await _log(db, body.who, "create" if new else "edit", ac_type)
    await db.commit()
    return to_json(a)


@app.post("/api/aircraft/{ac_type}/verify")
async def verify_aircraft(ac_type: str, body: VerifyIn, db=Depends(get_db)):
    a = await _get(db, ac_type)
    a.verified = True
    a.checked_by = body.who.strip().upper()[:16]
    a.checked_date = utcnow().strftime("%Y-%m-%d")
    a.updated_at = utcnow()
    a.updated_by = a.checked_by
    await _log(db, body.who, "verify", a.ac_type)
    await db.commit()
    return to_json(a)


@app.delete("/api/aircraft/{ac_type}/verify")
async def clear_verify(ac_type: str, who: str = "", db=Depends(get_db)):
    a = await _get(db, ac_type)
    a.verified = False
    a.checked_by = ""
    a.checked_date = ""
    a.updated_at = utcnow()
    await _log(db, who, "signoff_cleared", a.ac_type, "manual")
    await db.commit()
    return to_json(a)


@app.get("/api/changelog")
async def changelog(limit: int = 200, db=Depends(get_db)):
    rows = (await db.execute(select(ChangeLog).order_by(
        ChangeLog.at.desc()).limit(min(limit, 1000)))).scalars().all()
    return [{"at": r.at.isoformat() + "Z", "who": r.who, "action": r.action,
             "ac_type": r.ac_type, "detail": r.detail} for r in rows]


@app.get("/api/health")
async def health():
    return {"ok": True}
