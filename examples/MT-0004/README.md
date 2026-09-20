---
card: MT-0004
title: Purge scheduler
status: open
created_at: 2026-09-15
closed_at:
epic: MT-0002
parent: MT-0003
category: infra
branch:
agent_resume:
---

# MT-0004 — Purge scheduler

## What we want

Run the MT-0003 purge once a day, off peak, and record row counts.

## Why

A job that nobody schedules is a comment. The parent (MT-0003) is the SQL; this
card is how it actually runs.

## Origin

Decomposition of MT-0002; depends on MT-0003 existing as a callable job.
