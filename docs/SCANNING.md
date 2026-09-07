# Source scanning

`SourceScanService` is the orchestration layer that turns a source adapter into a repeatable market scan.

## Flow

```text
query
  -> source.discover()
  -> product refs
  -> source.snapshot() with bounded concurrency
  -> append-only snapshot repository
  -> deterministic TrendEngine
  -> compact scan result
```

A discovery failure stops the run because no candidate set exists. Detail failures are isolated per product and returned in `failures`, so one broken listing does not discard successful observations.

## API

When `GOOFISH_STATE_FILE` is configured, Goofish is registered automatically.

```bash
curl -X POST http://127.0.0.1:8000/v1/scans/goofish \
  -H 'content-type: application/json' \
  -d '{"query":"portable monitor","limit":20,"concurrency":3}'
```

Configured sources can be inspected with:

```bash
curl http://127.0.0.1:8000/v1/sources
```

The response intentionally contains compact measurable facts and trend signals. Raw source evidence remains in the persisted `ProductSnapshot` instead of being duplicated into every scan response.

## Building trends

The first scan creates the baseline observation. Run the same query later to create another observation for the same product IDs. The trend engine then calculates auditable values such as:

- `wants_count.delta`
- `wants_count.velocity_per_hour`
- `views_count.delta`
- `views_count.velocity_per_hour`
- `price.delta`
- acceleration once at least three usable observations exist

Unsupported facts remain `null`. In particular, Goofish `wants_count` and `views_count` are demand proxies and are never relabeled as `sales_count`.

## Scheduling

Scheduling is intentionally outside `SourceScanService`. A scheduler, worker, cron task, or future queue can call the same scan operation repeatedly without changing domain logic. This keeps acquisition cadence separate from evidence semantics.
