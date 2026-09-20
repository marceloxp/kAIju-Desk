# MT-0003 — memory

> Work trail: decisions, gotchas, where we stopped, paths that didn't work.

- Batch size 5_000, loop until `ROW_COUNT() = 0`.
- Dry-run is a `SELECT COUNT(*)` with the same `WHERE`.
