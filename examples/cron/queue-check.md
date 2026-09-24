---
when: 30 8 * * *
script: queue-check.sh
title: Queue check
readable: Every day at 08:30, send the queue size on Telegram
---

Sample workspace job. `kaiju gui` lists this file under Crons.
