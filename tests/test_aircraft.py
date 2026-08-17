import os, sys
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///./test_ac.db"
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import pytest, pytest_asyncio, httpx
from httpx import ASGITransport
import main as appmod


@pytest_asyncio.fixture
async def client():
    from database import engine
    await engine.dispose()
    if os.path.exists("test_ac.db"): os.remove("test_ac.db")
    async with appmod.app.router.lifespan_context(appmod.app):
        async with httpx.AsyncClient(transport=ASGITransport(app=appmod.app), base_url="http://t") as c:
            yield c
    from database import engine as e2
    await e2.dispose()
    if os.path.exists("test_ac.db"): os.remove("test_ac.db")


@pytest.mark.asyncio
async def test_seed_and_verify(client):
    r = await client.get("/api/aircraft")
    ac = r.json()["aircraft"]
    assert len(ac) == 43           # seeded from master
    a320 = next(x for x in ac if x["AC_TYPE"] == "A320")
    assert a320["VERIFIED"] == "NO"
    # verify live
    r = await client.post("/api/aircraft/A320/verify", json={"who": "sg"})
    assert r.json()["VERIFIED"] == "YES" and r.json()["CHECKED_BY"] == "SG"
    # editing a dimension clears the sign-off
    r = await client.put("/api/aircraft/A320", json={"AC_TYPE": "A320", "NOSE_TO_WING": 23.50, "who": "sg"})
    assert r.json()["VERIFIED"] == "NO"
    # new type
    r = await client.put("/api/aircraft/C25A", json={"AC_TYPE": "C25A", "LENGTH": 14.7,
        "WINGSPAN": 15.9, "NOSE_TO_WING": 7.0, "NOSE_HEIGHT": 2.0, "TAIL_HEIGHT": 4.6,
        "WING_HEIGHT": 2.5, "SOURCE": "estimate", "who": "sg"})
    assert r.status_code == 200
    r = await client.get("/api/aircraft")
    assert any(x["AC_TYPE"] == "C25A" for x in r.json()["aircraft"])
    # changelog recorded the actions
    r = await client.get("/api/changelog")
    actions = [e["action"] for e in r.json()]
    assert "verify" in actions and "signoff_cleared" in actions and "create" in actions
