# Consumer guide — app_stats

A consumer app polls one or more producer apps on a schedule, stores the ingested data
locally, and serves charts from local tables only.  The network call happens at ingest
time, not at chart render time.

---

## 1. Import the consumer submodule

The consumer tables are **not** imported by `ecodev_core.__init__`, so they are never
created in producer-only databases.  Import them explicitly in the consumer app:

```python
from ecodev_core.app_stats.consumer import (
    StatsApiClient,
    RemoteActivity,
    RemoteAppProject,
    delete_lookback_activities,
    delete_lookback_projects,
    upsert_remote_activities,
    upsert_remote_projects,
    get_remote_activities,
    get_remote_projects,
)
```

Add both table classes to the app's `db_model/__init__.py` so `create_db_and_tables`
creates them.

---

## 2. Add a producer registry

The registry can be driven from the database (preferred) or from a static env-var fallback.

### Database-first (preferred)

Store producer configs in a `StatsApiConfig` table (`app/db_model/stats_api_config.py`)
and read them with `get_stats_api_configs(session)`.  `resolve_registry()` in
`app/methodo/app_stats/ingest.py` checks the DB first and falls back to the constant
below only when the table is empty.  The table can be edited at runtime via the
Admin → API Config page without a service restart.

### Static fallback

In `app/constants.py`:

```python
import os

CF_TOOL_BASE_URL = os.getenv('CF_TOOL_BASE_URL', 'http://carbon_footprint_backend:80')
CF_TOOL_API_KEY  = os.getenv('CF_TOOL_API_KEY', '')

MYECOACT_BASE_URL = os.getenv('MYECOACT_BASE_URL', 'http://my_ecoact_backend:80')
MYECOACT_API_KEY  = os.getenv('MYECOACT_API_KEY', '')

REGISTRY_NAME    = 'name'
REGISTRY_BASE_URL = 'base_url'
REGISTRY_API_KEY  = 'api_key'

STATS_REGISTRY = [
    {REGISTRY_NAME: 'cf_tool',   REGISTRY_BASE_URL: CF_TOOL_BASE_URL,  REGISTRY_API_KEY: CF_TOOL_API_KEY},
    {REGISTRY_NAME: 'my_ecoact', REGISTRY_BASE_URL: MYECOACT_BASE_URL, REGISTRY_API_KEY: MYECOACT_API_KEY},
]

STATS_LOOKBACK_HOURS  = 24
STATS_LOOKBACK_MONTHS = 12
STATS_BACKFILL_DAYS   = 400
```

> **Production note:** The `/stats/*` routes are part of the **FastAPI** backend.
> Set `CF_TOOL_BASE_URL` etc. to the producer's `fastapi_url` in `.env`.  The Docker
> service name defaults only work when both apps share the same compose network.

---

## 3. Granularity: hour vs. month

The ingest has two granularities and both must be consistent across the fetch, delete, and
upsert calls for the delete scope to match the ingest scope:

| Grain | Schedule | Purpose |
|-------|----------|---------|
| `hour` | nightly 03:00 | Rolling 24-hour window of method calls |
| `month` | monthly 1st 04:00 | Pre-aggregated `unique_users` per (app, month, method) |

The `unique_users` field is computed server-side in the producer.  It is meaningful at
month grain (distinct users in a full calendar month) but counts distinct users only within
the 24-hour ingest window at hour grain, which is less useful for dashboards.

**Boundary rule:** pass the same `granularity` to `fetch_activities`,
`delete_lookback_activities`, and `upsert_remote_activities`.  If they diverge, the delete
removes rows for a different grain than the fetch produced, breaking idempotency.

For month grain the lookback must be **month-aligned** (first instant of the month).
`_default_lookback(MONTH_GRAIN)` handles this automatically using `month_start()`.

---

## 4. Write the ingest command

`app/methodo/app_stats/ingest.py` exposes four public helpers:

| Function | Purpose |
|---|---|
| `run_ingest(lookback, granularity)` | Poll all producers at one granularity; returns `[(app_name, count, error_or_None), ...]` |
| `run_ingest_all_grains()` | Calls `run_ingest` for every grain; returns `{granularity: [...]}` |
| `run_ingest_for_app(entry, lookback, granularity)` | Single-app ingest; returns `(count, error_or_None)` |
| `run_ingest_for_app_all_grains(entry)` | Single-app ingest at every grain; raises `RuntimeError` on failure |

`resolve_registry()` is the single source of truth for the producer list — DB rows take
precedence over the `STATS_REGISTRY` fallback.

Each producer is ingested independently.  A network failure on one app is caught and
reported without aborting the others.  The session is rolled back on error so partial
writes are never committed.

### Typical Typer command

```python
# app/typer_app.py
import typer
from ecodev_core.app_stats.constants import HOUR_GRAIN, MONTH_GRAIN
from app.methodo.app_stats import run_ingest, run_ingest_all_grains

@typer_app.command()
def ingest_remote_analytics(
    granularity: str = typer.Option(HOUR_GRAIN),
    backfill: bool = typer.Option(False),
) -> None:
    if backfill:
        results = run_ingest_all_grains()
    else:
        results = {granularity: run_ingest(granularity=granularity)}
    for grain, rows in results.items():
        for app_name, count, error in rows:
            if error:
                typer.echo(f'[{grain}] {app_name}: ERROR — {error}')
            else:
                typer.echo(f'[{grain}] {app_name}: {count} rows ingested')
```

### Low-level reference

`_ingest_one` handles one producer at one granularity:

1. Skips the producer if `api_key` is empty (logs a warning, returns `(0, message)`).
2. Calls `fetch_activities` with `group_by_method=True, group_by_application=True`
   at hour grain; clears both flags at month grain so `unique_users` is aggregated
   across methods.
3. Deletes the matching window and upserts the fresh rows.
4. At hour grain only, fetches projects.  A `None` response (producer has no projects
   endpoint) leaves stored rows untouched; an empty list replaces them with nothing.

---

## 5. Onboarding a new producer

The rolling 24-hour window does **not** automatically back-fill history.  When adding a new
producer for the first time, run a one-off backfill command before the next cron fires:

```bash
# Back-fill 12 months of history
python -m app.typer_app ingest-remote-analytics --backfill

# Or specify an explicit window
python -m app.typer_app ingest-remote-analytics --lookback-hours 720
```

---

## 6. Schedule the ingest with Ofelia

In `docker-compose.yml`, add Ofelia labels to the app service:

```yaml
labels:
  ofelia.enabled: "true"
  ofelia.job-exec.ingest-remote-analytics.schedule: "0 0 3 * * *"
  ofelia.job-exec.ingest-remote-analytics.command: "python -m app.typer_app ingest-remote-analytics"
  ofelia.job-exec.ingest-remote-analytics-monthly.schedule: "0 0 4 1 * *"
  ofelia.job-exec.ingest-remote-analytics-monthly.command: "python -m app.typer_app ingest-remote-analytics --granularity month"
```

The hour-grain job runs nightly at 03:00.  The month-grain job runs on the 1st of each
month at 04:00.  History stored outside the 24-hour window is **retained** —
`delete_lookback_activities` only removes rows at or after `lookback` **for the matching
granularity**, so hour-grain and month-grain rows are never mixed.

---

## 7. Reading ingested data

Both helpers return `list[dict]`, which callers can pass directly to `pd.DataFrame`:

```python
import pandas as pd
from ecodev_core.app_stats.constants import HOUR_GRAIN, MONTH_GRAIN
from ecodev_core.app_stats.consumer import get_remote_activities, get_remote_projects

with Session(engine) as session:
    # Hour-grain activities (default)
    df_activities = pd.DataFrame(get_remote_activities(session, application='cf_tool'))

    # Month-grain activities (unique_users is meaningful here)
    df_monthly = pd.DataFrame(
        get_remote_activities(session, application='cf_tool', granularity=MONTH_GRAIN)
    )

    # Optional date filters
    df_recent = pd.DataFrame(
        get_remote_activities(session, from_date=some_dt, to_date=other_dt)
    )

    # All apps, or filter to one
    df_projects = pd.DataFrame(get_remote_projects(session))
    df_app_projects = pd.DataFrame(get_remote_projects(session, application='cf_tool'))
```

`fetch_projects` is a single request (no pagination), so its return value is already the
complete set — or `None` if the producer exposes no projects endpoint.

---

## 8. Cross-references

- Producer guide: `docs/producer_guide.md`
- Consumer tables: `ecodev_core/app_stats/consumer/tables.py`
- Ingest helpers: `ecodev_core/app_stats/consumer/ingest.py`
- Dict helpers: `ecodev_core/app_stats/consumer/processing.py`
- DB config table: `app/db_model/stats_api_config.py`
- Ingest logic: `app/methodo/app_stats/ingest.py`
