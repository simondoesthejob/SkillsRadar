-- How many postings each source delivered per day (last 14 days), and how many were distinct.
-- Several runs on one day, or the same vacancy on consecutive days, show up as extra rows.
SELECT
  dt,
  source,
  count(*) AS rows_ingested,
  count(DISTINCT dedupe_key) AS distinct_postings
FROM raw_postings
WHERE dt >= date_format(date_add('day', -14, current_date), '%Y-%m-%d')
GROUP BY dt, source
ORDER BY dt DESC, source;
