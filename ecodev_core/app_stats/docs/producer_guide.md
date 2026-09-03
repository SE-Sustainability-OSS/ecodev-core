# Producer guide — app_stats

Any app using `ecodev_core` can expose its usage statistics over HTTP by wiring
`get_stats_router()` into its FastAPI instance.  One endpoint is always registered
(`/stats/activities`).  A second endpoint (`/stats/projects`) is registered only when
the app passes a `ProjectStatsAdapter`.

---

## 1. Add the `stats_api` config section

In every environment config (`config/local.yaml`, `config/preprod.yaml`, `config/prod.yaml`):

```yaml
stats_api:
   api_key: "replace-with-a-secret"
```

**The key is mandatory.**  An absent or null value means every inbound request is rejected
with HTTP 401.  There is no JWT fallback.

### Generating a key

Run once per environment:

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

This produces a 64-character hex string.  Never commit real keys to version control;
inject them via environment variable or a secrets manager.

---

## 2. Wire the router — activities only

For apps that own no project table:

```python
# app/app.py
from ecodev_core import get_stats_router

app.include_router(get_stats_router())
```

`/stats/activities` is now live.  `GET /stats/projects` returns **404** because no adapter
was supplied.

---

## 3. Wire the router — with projects (cf-tool pattern)

For apps that own a `Project` model:

```python
# app/routers/app_stats.py
from datetime import datetime
from typing import Iterable

from sqlmodel import col, select, Session

from ecodev_core import get_stats_router, ProjectExport, ProjectStatsAdapter

from app.db_model import Project


def _list_projects(
        session: Session,
        from_date: datetime | None,
        to_date: datetime | None,
) -> Iterable[ProjectExport]:
    stmt = select(Project)
    if from_date:
        stmt = stmt.where(col(Project.modified_at) >= from_date)
    if to_date:
        stmt = stmt.where(col(Project.modified_at) < to_date)

    for project in session.exec(stmt).all():
        yield ProjectExport(
            project_id=str(project.id),
            name=project.name,
            creator=project.user,
            created_at=project.created_at,
            modified_at=project.modified_at,
            description=getattr(project, 'description', None),
            client=getattr(project, 'client', None),
            project_type=getattr(project, 'project_type', None),
        )


stats_router = get_stats_router(
    adapter=ProjectStatsAdapter(list_projects=_list_projects)
)
```

> **Filter on `modified_at`, not `created_at`.**  The consumer sends the last-ingest
> timestamp as `from_date`; filtering on `modified_at` ensures projects updated since the
> last ingest are included, not just projects created since then.

```python
# app/app.py
from app.routers.app_stats import stats_router
app.include_router(stats_router)
```

---

## 4. Endpoint shapes and query surface

### `/stats/activities` → `PagedResponse[ActivityExport]`

Rows are aggregated server-side by `(application, period_start, method)` with `count(*)`
as `activity_count` and `count(distinct user)` as `unique_users`.  No raw user identity
crosses the wire.

| Query parameter | Type                  | Default  | Description                    |
| --------------- | --------------------- | -------- | ------------------------------ |
| `from_date`   | ISO-8601 datetime     | —       | Inclusive bucket start filter  |
| `to_date`     | ISO-8601 datetime     | —       | Exclusive bucket end filter    |
| `method`      | string                | —       | Filter to a single method name |
| `page_size`   | int (1–5000)         | 500      | Max rows per page              |
| `granularity` | `hour` or `month` | `hour` | Bucket size for`date_trunc`  |

The response envelope is:

```json
{
  "items": [...],
  "next_from_date": "2026-01-15T09:00:00" | null
}
```

Pass `next_from_date` back as `from_date` to fetch the next page.  When `next_from_date`
is `null` the final page has been reached.  `next_from_date` is a keyset cursor on the
bucket timestamp, so pages remain stable while new activity arrives.

### `/stats/projects` → `list[ProjectExport]`

Returns a bare JSON array (no pagination envelope).  All projects matching the date filters
are returned in a single response.

When no adapter is supplied the route is not registered at all and returns **404**.  This is
a valid opt-out, not an error: the consumer client treats it as "this producer has no
projects" and leaves any previously stored rows untouched.

| Query parameter | Type              | Default | Description                           |
| --------------- | ----------------- | ------- | ------------------------------------- |
| `from_date`   | ISO-8601 datetime | —      | Filter by`modified_at >= from_date` |
| `to_date`     | ISO-8601 datetime | —      | Filter by`modified_at < to_date`    |

---

## 5. Custom dependency

`get_stats_router` accepts a `dependency` kwarg if you need to swap the auth check:

```python
stats_router = get_stats_router(dependency=my_custom_auth)
```

The default is `api_key_auth` from `ecodev_core.app_stats.api_key`.

---

## 6. Remove the legacy `/get-activities` endpoint

The new `/stats/activities` supersedes it.  Delete or comment out any existing
`@app.get('/get-activities')` decorator in `app/app.py`.
