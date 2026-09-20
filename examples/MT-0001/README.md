---
card: MT-0001
title: Indexes on created_at
status: done
created_at: 2026-09-12
closed_at: 2026-09-19
epic:
parent:
category: database
branch: feature/created-at-indexes
agent_resume:
---

# MT-0001 — Indexes on created_at

## What we want

Add indexes on `created_at` for the tables that the purge job will filter by
date, starting with `exceptions`.

## Why

Full scans on `created_at` dominate the slow query log. Retention work
(MT-0002) cannot start from a sequential read of 14 GB.

## Origin

Backlog: DATA_FREE of ~14 GB in exceptions (still open there; this card only
covers the indexes).
