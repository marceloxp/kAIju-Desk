# MT-0001 — delivery

## What was done

Created `exceptions_created_at` (`created_at`) on `exceptions`. Checked with
`EXPLAIN` that the retention date filter uses the index.

## Result

The sample query in `sql/explain.sql` went from a full scan to a range scan.
Human approved 2026-09-19.

## What was left out

Other tables named in the slow log. New cards if they still matter after the
purge exists.
