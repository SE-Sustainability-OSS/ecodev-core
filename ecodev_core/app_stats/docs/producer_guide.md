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
   api_key: null   # replace with a non-null secret in preprod / prod
```

If the section is absent, the endpoint falls back to monitoring-JWT auth and logs a
deprecation warning on every call.  This keeps existing deployments working on upgrade.

---

## 2. Wire the router — activities only

For apps that own no project table (myecoapps, cdp-tool analytics):

```python
# app/app.py
from ecodev_core import get_stats_router

app.include_router(get_stats_router())
```

`/stats/activities` is now live.  `GET /stats/projects` returns **404** because no adapter was supplied.

---

## 3. Wire the router — with projects (cf-tool pattern)

For apps that own a `Project` model inheriting `ProjectBase` from `ecoact-access`:

```python
# app/routers/app_stats.py
from datetime import datetime
from typing import Iterable

from sqlmodel import col, select, Session

from ecodev_core import get_stats_router, ProjectExport, ProjectStatsAdapter

from app.db_model import Project, ProjectAccess


def _list_projects(
        session: Session,
        from_date: datetime | None,
        to_date: datetime | None,
) -> Iterable[ProjectExport]:
    stmt = select(Project)
    if from_date:
        stmt = stmt.where(col(Project.created_at) >= from_date)
    if to_date:
        stmt = stmt.where(col(Project.created_at) < to_date)

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

```python
# app/app.py
from app.routers.app_stats import stats_router
app.include_router(stats_router)
```

---

## 4. Foreign-schema pattern (cdp-tool style)

When the project table lives in another schema or is owned by a different library,
use SQLAlchemy's `extend_existing=True` to create a read-only model without migrating:

```python
from sqlmodel import Field, SQLModel

class ProjectReadModel(SQLModel, table=True):
    __tablename__ = 'project'
    __table_args__ = {'extend_existing': True}
    id: int = Field(primary_key=True)
    name: str
    created_by: str
    ...
```

Then pass a `list_projects` callable that queries `ProjectReadModel`.

---

## 5. Remove the legacy `/get-activities` endpoint

The new `/stats/activities` supersedes it.  Delete or comment out any existing
`@app.get('/get-activities')` decorator in `app/app.py`.

---

## 6. Curated monitoring (cf-tool)

Monitoring is off by default.  Pass `monitoring=True` on a curated set of high-value
callbacks (page loads, computations, uploads, exports).  Fix hardcoded application names
to use `SETTINGS.app_name`.

A global `monitoring=True` on all ~150 callbacks would write a DB row on every interaction;
deliberately limit it to the actions that provide signal.

---

## 7. API key vs. monitoring JWT

`X-API-Key` is the primary auth path.  Consumer apps send the key configured in their
registry.  The monitoring JWT fallback is accepted for one release only and will be
removed in a future version.

### Generating and provisioning a key

**Step 1 — Generate a cryptographically random secret**

Run once per environment (local, preprod, prod):

```bash
python -c "import secrets; print(secrets.token_hex(32))"
```

This produces a 64-character hex string, e.g.:
```
a3f8e2c17b094d56a1e3f72c84d09b351f4a8e6c2d07b3a91e4f52c86d0a7b3
```

**Step 2 — Set the key on the producer side**

Place the generated value in every environment config under `stats_api.api_key`:

```yaml
# config/local.yaml  (or preprod.yaml / prod.yaml)
stats_api:
  api_key: "a3f8e2c17b094d56a1e3f72c84d09b351f4a8e6c2d07b3a91e4f52c86d0a7b3"
```

> **Security note**: never commit real keys to version control.  Inject them via
> environment variable or a secrets manager and reference them from the YAML with
> `${ENV_VAR}` substitution if your config loader supports it.

**Step 3 — Set the same key on the consumer side**

The consumer (e.g. `ecoact-myecoapps` or `ecoact-cf-tool`) stores the key in its own
`.env` under a name matching the registry entry, e.g.:

```bash
# .env on the consumer app
CF_TOOL_API_KEY="a3f8e2c17b094d56a1e3f72c84d09b351f4a8e6c2d07b3a91e4f52c86d0a7b3"
```

Each producer–consumer pair uses its **own** independent key; do not reuse a key across
multiple producer apps.
