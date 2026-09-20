---
card: MT-0003
title: Purge job
status: open
created_at: 2026-09-15
closed_at:
epic: MT-0002
parent:
category: database
branch:
agent_resume:
---

# MT-0003 — Purge job

## What we want

A SQL job that deletes `exceptions` older than 30 days, in small batches, using
the `created_at` index from MT-0001.

## Why

The epic (MT-0002) needs a reversible, countable delete. Not a `TRUNCATE`.

## Origin

Decomposition of MT-0002.
