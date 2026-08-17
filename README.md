# IFP Aircraft Data service

A small shared store for aircraft reference dimensions and their verification
status, used by the CAP 1732 taxi-route obstacle tool. Sibling of the other IFP
tools but deliberately simpler: **no login** (open by design — the data is
non-sensitive and the team wants frictionless access) and **no locking** (a
44-row reference table edited occasionally; last-write-wins). Sign-offs record
typed initials.

## What it stores
One `aircraft` table (type, six dimensions, source, verified + who/when) plus a
change log. On first boot it seeds itself from `seed_aircraft.json` (the master
list extracted from the tool). After that the database is the source of truth.

## API
- `GET  /api/aircraft` — the full list (the tool loads this on startup)
- `PUT  /api/aircraft/{type}` — create/update dimensions; editing a dimension of
  a verified type clears its sign-off
- `POST /api/aircraft/{type}/verify` — mark verified (body: `{"who":"SG"}`)
- `DELETE /api/aircraft/{type}/verify` — clear the sign-off
- `GET  /api/changelog` — recent changes
- `GET  /api/health`

## Deploy to Railway
1. Push this folder to a GitHub repo (e.g. `ifp-aircraft-service`).
2. Railway → New Project → Deploy from GitHub repo → this repo.
3. Add a **PostgreSQL** service; on the app service set `DATABASE_URL` to
   `${{Postgres.DATABASE_URL}}` (reference picker). Enable Postgres backups.
4. Build is Nixpacks + `requirements.txt`; the Procfile starts uvicorn.
5. Generate a public domain. Note the `*.up.railway.app` URL — the tool needs it.

`CORS_ORIGINS` defaults to `*` (any site may call it). If you'd rather lock it to
the portal/tool origin later, set it to that origin.

## Point the tool at it
In the tool's `index.html`, set the `AIRCRAFT_API` constant (near the top of the
main script) to your Railway URL, or define `window.AIRCRAFT_API_URL` before the
script runs. If unset or unreachable, the tool falls back to its built-in list
and works offline (sign-offs stay local until reconnected).

## Local run
```
pip install -r requirements.txt
uvicorn main:app --reload
python -m pytest tests/
```
