# Contributing — Team Vayu-X

Working agreement for Team 152. Keep it light, keep `main` demo-ready at all times.

## Branching

```
main     ← always demo-ready. Never push directly.
 └ dev   ← integration branch. All feature branches merge here first.
    ├ feat/<scope>-<short-desc>
    ├ fix/<scope>-<short-desc>
    ├ docs/<short-desc>
    └ chore/<short-desc>
```

`<scope>` is the service: `frontend`, `backend`, `ai-model`, `alerts`, `pipeline`, `infra`.

```bash
git checkout dev && git pull
git checkout -b feat/ai-model-convlstm-track
```

## Commit messages (Conventional Commits)

```
<type>(<scope>): <imperative summary>
```

| Type | Use for |
|---|---|
| `feat` | New capability |
| `fix` | Bug fix |
| `docs` | Documentation only |
| `refactor` | Restructure, no behaviour change |
| `perf` | Performance |
| `test` | Tests |
| `chore` | Build, deps, tooling |

Examples:

```
feat(ai-model): add ConvLSTM track prediction head
fix(backend): correct bbox filter on /cyclones endpoint
docs(readme): add MOSDAC access instructions
```

## Pull requests

1. Rebase on `dev` before opening.
2. Run `make lint && make test` locally — CI runs the same.
3. Fill the PR template: what changed, why, how it was tested.
4. One reviewer from another sub-team (cross-review catches integration breaks).
5. Squash-merge into `dev`.

## Code standards

**Python** — `ruff` for lint + format, `mypy` where practical.

```bash
ruff check . --fix && ruff format .
```

- Type-hint all public functions.
- Pydantic models for every API boundary.
- No hard-coded paths, URLs, or credentials — read from config/env.

**JavaScript / React** — `eslint` + `prettier`.

```bash
npm run lint && npm run format
```

- Functional components + hooks only.
- Data fetching lives in `src/services/`, never inline in components.
- Component files `PascalCase.jsx`, hooks `useCamelCase.js`.

## Hard rules

| Rule | Why |
|---|---|
| Never commit `.env` or any credential | Public repo — leaked keys are unrecoverable |
| Never commit satellite data, model weights, or `*.nc` / `*.h5` / `*.pt` | Repo bloat; use MinIO / release assets |
| Never commit notebook outputs | Clear outputs before committing |
| Changes to `shared/schemas/` need agreement from both sides of the contract | Breaking a schema breaks other services silently |
| Any new env var goes into `.env.example` in the same PR | Otherwise teammates' local stack breaks |

## Local setup

```bash
cp .env.example .env
docker compose up --build      # full stack
# or per-service — see each service's README.md
```

## Who owns what

| Area | Path | Owner |
|---|---|---|
| Dashboard | `frontend/` | _TBD_ |
| API gateway | `backend/` | _TBD_ |
| Models & training | `ai-model/` | _TBD_ |
| Ingestion & ETL | `data-pipeline/` | _TBD_ |
| Alerts | `alert-system/` | _TBD_ |
| Infra & CI | `infra/`, `.github/` | _TBD_ |

Ping the owner before making structural changes to their area.
