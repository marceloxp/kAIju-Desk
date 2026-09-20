-- Sample date filter the purge job will run.
-- After MT-0001: range scan on exceptions_created_at.
EXPLAIN
SELECT id
FROM exceptions
WHERE created_at < DATE_SUB(UTC_DATE(), INTERVAL 30 DAY);
