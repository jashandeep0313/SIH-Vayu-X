# shared/ — Service contracts

The single source of truth for data exchanged between services. **These schemas are the reason the
five sub-teams can build in parallel** — every team mocks against the schema and integrates late
with low risk.

## Schemas

| File | Object | Produced by | Consumed by |
|---|---|---|---|
| [`schemas/cyclone_event.schema.json`](schemas/cyclone_event.schema.json) | `CycloneEvent` | `ai-model` | `backend`, `alert-system`, `frontend` |
| [`schemas/forecast.schema.json`](schemas/forecast.schema.json) | `Forecast` | `ai-model` | `backend`, `alert-system`, `frontend` |
| [`schemas/alert.schema.json`](schemas/alert.schema.json) | `Alert` | `alert-system` | `backend`, `frontend`, external webhooks |

## Rules

1. **Change the schema before the code.** Both sides of a contract must agree first.
2. **Additive changes only** within a version — new optional fields are safe; renaming, removing,
   or retyping a field is breaking.
3. **Breaking change → new API version** (`/api/v2`), never a silent mutation.
4. A schema change needs review from an owner on **both** sides of the contract.

## Conventions

| Aspect | Convention |
|---|---|
| Timestamps | ISO-8601 UTC, `2025-09-08T12:30:00Z` |
| Coordinates | Decimal degrees WGS-84, `lat` before `lon` |
| Geometry | GeoJSON (`Point`, `LineString`, `Polygon`) |
| Wind speed | Knots (`_kt`) — convert for display only |
| Pressure | Hectopascals (`_hpa`) |
| Distance | Kilometres (`_km`) |
| Identifiers | UUID v4 |
| Field naming | `snake_case`, units in the suffix |

## Validating a payload

```bash
pip install check-jsonschema
check-jsonschema --schemafile shared/schemas/cyclone_event.schema.json sample_event.json
```

In Python:

```python
import json
from jsonschema import validate

schema = json.load(open("shared/schemas/cyclone_event.schema.json"))
validate(instance=payload, schema=schema)
```

CI validates fixture payloads against these schemas on every push, so a contract drift fails the
build rather than surfacing during integration.
