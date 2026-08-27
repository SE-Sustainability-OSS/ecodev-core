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
    get_activities_df,
    get_projects_df,
)
```

Add both table classes to the app's `db_model/__init__.py` so `create_db_and_tables`
creates them.

---

## 2. Add a producer registry

In `app/constants.py` (following the existing `CDP_API_URL` convention):

```python
import os

CF_TOOL_BASE_URL = os.getenv('CF_TOOL_BASE_URL', 'http://carbon_footprint_backend:80')
CF_TOOL_API_KEY  = os.getenv('CF_TOOL_API_KEY', '')

MYECOACT_BASE_URL = os.getenv('MYECOACT_BASE_URL', 'http://my_ecoact_backend:80')
MYECOACT_API_KEY  = os.getenv('MYECOACT_API_KEY', '')

STATS_REGISTRY = [
    {'name': 'cf_tool',   'base_url': CF_TOOL_BASE_URL,   'api_key': CF_TOOL_API_KEY},
    {'name': 'my_ecoact', 'base_url': MYECOACT_BASE_URL,   'api_key': MYECOACT_API_KEY},
]
```

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
from app.constants import STATS_REGISTRY

LOOKBACK_DAYS = 400


def run_ingest() -> None:
    lookback = datetime.utcnow() - timedelta(days=LOOKBACK_DAYS)
    with Session(engine) as session:
        for entry in STATS_REGISTRY:
            client = StatsApiClient(entry['base_url'], entry['api_key'])
            app_name = entry['name']

            activities = list(client.fetch_activities(from_date=lookback))
            delete_lookback_activities(session, app_name, lookback)
            upsert_remote_activities(session, app_name, activities)

            projects = list(client.fetch_projects())
            delete_lookback_projects(session, app_name)
            upsert_remote_projects(session, app_name, projects)
```

---

## 4. Schedule the ingest with Ofelia

In `docker-compose.yml`, add Ofelia labels to the app service:

```yaml
labels:
  ofelia.enabled: "true"
  ofelia.job-exec.ingest-remote-analytics.schedule: "0 0 */6 * * *"
  ofelia.job-exec.ingest-remote-analytics.command: "python -m app.methodo.app_stats.ingest"
```

This runs every 6 hours.  The 400-day lookback window ensures back-filled or corrected
rows are picked up on the next cycle.

---

## 5. Pre-aggregation mart (`analytics_hourly_fact`)

The mart lives in the consumer app, not in `ecodev_core`.  Build it from the union of
local `AppActivity` and `RemoteHourlyActivity` after each ingest cycle.

Suggested grain: `(hour, user_email, application, method, relevant_option)` with
`activity_count`.  Keep `user_email` in the grain — seven of the eleven analytics charts
need `count(distinct user_email)`, which cannot be recovered from summed rows.

`rbu` and `team` are joined from `app_user_profile` at query time (not denormalised),
so a profile edit is reflected immediately without a mart rebuild.

---

## 6. Chart retrievers

Place all chart queries behind thin retriever functions in
`app/db_model/retrievers/analytics.py`.  This keeps the storage engine swappable
(revisit DuckDB past ~50 M fact rows) and keeps callbacks free of SQL.

```python
# app/db_model/retrievers/analytics.py
from sqlmodel import func, col, select, Session
from app.db_model import AnalyticsHourlyFact

def monthly_unique_users(session: Session) -> list[tuple]:
    return session.exec(
        select(
            func.date_trunc('month', col(AnalyticsHourlyFact.hour)).label('month'),
            func.count(func.distinct(col(AnalyticsHourlyFact.user_email))).label('users'),
        ).group_by(func.date_trunc('month', col(AnalyticsHourlyFact.hour)))
        .order_by(func.date_trunc('month', col(AnalyticsHourlyFact.hour)))
    ).all()
```

---

## 7. Cross-references

- Producer guide: `docs/producer_guide.md`
- Demo notebook: `notebooks/app_stats_demo.ipynb`
- Consumer tables: `ecodev_core/app_stats/consumer/tables.py`
- Ingest helpers: `ecodev_core/app_stats/consumer/ingest.py`
- DataFrame helpers: `ecodev_core/app_stats/consumer/processing.py`
