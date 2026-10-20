-- How often the same posting is ingested more than once (repeat runs, or a vacancy that stays
-- advertised for days). An average of 1.0 means no repeats. Cross-source duplicates (the same
-- job on Adzuna and Reed) cannot be seen here; they need the fuzzy matching planned for the
-- curation job.
SELECT
  source,
  count(*) AS rows_ingested,
  count(DISTINCT dedupe_key) AS distinct_postings,
  round(1.0 * count(*) / count(DISTINCT dedupe_key), 2) AS avg_copies_per_posting
FROM raw_postings
GROUP BY source
ORDER BY source;
