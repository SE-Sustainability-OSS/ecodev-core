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
    RemoteHourlyActivity,
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

## 3. Write the ingest command

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
from app.constants import STATS_REGISTRY, STATS_LOOKBACK_HOURS


def run_ingest(lookback: datetime | None = None) -> None:
    if lookback is None:
        lookback = datetime.utcnow().replace(minute=0, second=0, microsecond=0) \
                   - timedelta(hours=STATS_LOOKBACK_HOURS)

    with Session(engine) as session:
        for entry in STATS_REGISTRY:
            client = StatsApiClient(base_url=entry['base_url'], api_key=entry['api_key'])
            app_name = entry['name']

            activities = list(client.fetch_activities(from_date=lookback))
            delete_lookback_activities(session, app_name, lookback)
            upsert_remote_activities(session, app_name, activities)

            projects = list(client.fetch_projects())
            delete_lookback_projects(session, app_name)
            upsert_remote_projects(session, app_name, projects)
```

The same `lookback` value is passed to both `fetch_activities` and `delete_lookback_activities`.
This is intentional: the delete scope matches the fetch scope exactly, so a re-run of the
same window replaces identical data (idempotent).

---

## 4. Onboarding a new producer

The rolling 24-hour window does **not** automatically back-fill history.  When adding a new
producer for the first time, run a one-off backfill command before the next cron fires:

```bash
# Back-fill 400 days of history
python -m app.typer_app ingest-remote-analytics --backfill

# Or specify an explicit window
python -m app.typer_app ingest-remote-analytics --lookback-hours 720
```

---

## 5. Schedule the ingest with Ofelia

In `docker-compose.yml`, add Ofelia labels to the app service:

```yaml
labels:
  ofelia.enabled: "true"
  ofelia.job-exec.ingest-remote-analytics.schedule: "0 0 3 * * *"
  ofelia.job-exec.ingest-remote-analytics.command: "python -m app.typer_app ingest-remote-analytics"
```

This runs nightly at 03:00, a quiet window that avoids active-user overlap so no overlap
margin is needed.  History already stored outside the 24-hour window is **retained** —
`delete_lookback_activities` only removes rows at or after `lookback`.

---

## 6. Reading ingested data

Both helpers return `list[dict]`, which callers can pass directly to `pd.DataFrame`:

```python
import pandas as pd
from ecodev_core.app_stats.consumer import get_remote_activities, get_remote_projects

with Session(engine) as session:
    df_activities = pd.DataFrame(get_remote_activities(session, application='cf_tool'))
    df_projects   = pd.DataFrame(get_remote_projects(session))
```

---

## 7. Cross-references

- Producer guide: `docs/producer_guide.md`
- Consumer tables: `ecodev_core/app_stats/consumer/tables.py`
- Ingest helpers: `ecodev_core/app_stats/consumer/ingest.py`
- Dict helpers: `ecodev_core/app_stats/consumer/processing.py`
