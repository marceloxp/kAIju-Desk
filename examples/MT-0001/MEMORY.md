# MT-0001 — memory

> Work trail: decisions, gotchas, where we stopped, paths that didn't work.

- `EXPLAIN` on the date filter was `type: ALL` before the index; after,
  `range` on `exceptions_created_at`.
- A composite `(tenant_id, created_at)` was considered and dropped: the purge
  is global, not per tenant.
- Building the index with `ALGORITHM=INPLACE, LOCK=NONE` succeeded on the
  replica first, then on primary during a quiet window.
