# MT-0002 — memory

> Work trail: decisions, gotchas, where we stopped, paths that didn't work.

- Policy: 30 days from `created_at`, UTC. No legal hold on this table.
- Rebuild-the-table was dropped in the backlog (too risky).
- Split: MT-0003 is the purge SQL; MT-0004 is the scheduler that calls it.
- Stopped at: waiting on MT-0003 to have a dry-run that only counts rows.
