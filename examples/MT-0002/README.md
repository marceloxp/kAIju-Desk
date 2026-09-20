---
card: MT-0002
title: Exception retention
status: in-progress
created_at: 2026-09-12
closed_at:
epic: MT-0002
parent:
category: database
branch: feature/exception-retention
agent_resume:
---

# MT-0002 — Exception retention

## What we want

Keep `exceptions` for 30 days, then drop the rows. Indexes (MT-0001) are in
place; this epic is the policy and the job.

## Why

DATA_FREE around 14 GB and growing. The table is a log, not a ledger.

## Origin

Backlog finding still open: DATA_FREE of ~14 GB in exceptions.
