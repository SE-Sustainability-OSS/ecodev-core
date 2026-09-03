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

Store producer configs in a `StatsApiConfig` table and read them with
`get_stats_api_configs(session)`.  The consumer's `_resolve_registry` helper checks the DB
first and falls back to the constant below only when the table is empty.

### Static fallback

In `app/constants.py`:

```python
import os

CF_TOOL_BASE_URL = os.getenv('CF_TOOL_BASE_URL', 'http://carbon_footprint_backend:80')
CF_TOOL_API_KEY  = os.getenv('CF_TOOL_API_KEY', '')

MYECOACT_BASE_URL = os.getenv('MYECOACT_BASE_URL', 'http://my_ecoact_backend:80')
MYECOACT_API_KEY  = os.getenv('MYECOACT_API_KEY', '')

STATS_REGISTRY = [
    {'name': 'cf_tool',   'base_url': CF_TOOL_BASE_URL,  'api_key': CF_TOOL_API_KEY},
    {'name': 'my_ecoact', 'base_url': MYECOACT_BASE_URL, 'api_key': MYECOACT_API_KEY},
]

STATS_LOOKBACK_HOURS = 24
STATS_BACKFILL_DAYS  = 400
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

---

## 4. Write the ingest command

```python
# app/methodo/app_stats/ingest.py
from datetime import datetime, timedelta

from sqlmodel import Session
from ecodev_core import engine
from ecodev_core.app_stats.consumer import (
    StatsApiClient,
    delete_lookback_activities, delete_lookback_projects,
    upsert_remote_activities, upsert_remote_projects,
)
from ecodev_core.app_stats.constants import HOUR_GRAIN
from app.constants import STATS_REGISTRY, STATS_LOOKBACK_HOURS


def run_ingest(lookback: datetime | None = None, granularity: str = HOUR_GRAIN) -> None:
    if lookback is None:
        lookback = datetime.utcnow().replace(minute=0, second=0, microsecond=0) \
                   - timedelta(hours=STATS_LOOKBACK_HOURS)

    with Session(engine) as session:
        for entry in STATS_REGISTRY:
            client = StatsApiClient(base_url=entry['base_url'], api_key=entry['api_key'])
            app_name = entry['name']

            activities = list(client.fetch_activities(from_date=lookback, granularity=granularity))
            delete_lookback_activities(session, app_name, lookback, granularity=granularity)
            upsert_remote_activities(session, app_name, activities, granularity=granularity)

            if granularity == HOUR_GRAIN:
                projects = client.fetch_projects()
                if projects is not None:
                    delete_lookback_projects(session, app_name)
                    upsert_remote_projects(session, app_name, projects)
```

`fetch_projects` returns `None` when the producer does not expose `/stats/projects`, which
is distinct from returning `[]`.  Skip the delete in the `None` case: a producer that never
had the endpoint has nothing stored anyway, and one whose route is temporarily
misconfigured keeps its existing rows instead of having them silently cleared.

The same `lookback` and `granularity` reach both the fetch and the delete, so a re-run of
the same window replaces identical rows (idempotent).  `delete_lookback_activities` removes
rows where `application == app_name AND granularity == granularity AND period_start >= lookback`
for the matching granularity only.  `delete_lookback_projects` removes all project rows for
the application (full replacement every hour-grain cycle).

---

## 5. Onboarding a new producer

The rolling 24-hour window does **not** automatically back-fill history.  When adding a new
producer for the first time, run a one-off backfill command before the next cron fires:

```bash
# Back-fill 400 days of history
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
    df_projects = pd.DataFrame(get_remote_projects(session))
```

`fetch_projects` is a single request (no pagination), so its return value is already the
complete set — or `None` if the producer exposes no projects endpoint.

---

## 8. Cross-references

- Producer guide: `docs/producer_guide.md`
- Consumer tables: `ecodev_core/app_stats/consumer/tables.py`
- Ingest helpers: `ecodev_core/app_stats/consumer/ingest.py`
- Dict helpers: `ecodev_core/app_stats/consumer/processing.py`
