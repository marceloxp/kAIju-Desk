# Backlog

> Findings that are not cards yet. Rules: `kaiju guide`.

## Open

### DATA_FREE of ~14 GB in exceptions

Seen on 2026-09-19 in `information_schema.TABLES`. Not a card yet: first we
want indexes on `created_at` (MT-0001) and a retention story (MT-0002).

## Dropped

### Rebuild the whole exceptions table

Too risky for a production table of this size. Indexes and a purge job are the
path. Dropped on 2026-09-12.
