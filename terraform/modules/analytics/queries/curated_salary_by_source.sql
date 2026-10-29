-- Advertised annual salary by source and salary_basis (annual_reported and daily_reported come
-- from the source's own pay period; daily_inferred and hourly_inferred are guessed from size).
-- Predicted salaries (Adzuna's own estimates) are excluded. A posting that stays advertised for days is counted once: the
-- ROW_NUMBER keeps only its most recent day.
WITH latest AS (
  SELECT
    *,
    row_number() OVER (PARTITION BY dedupe_key ORDER BY dt DESC) AS rn
  FROM curated_postings
)
SELECT
  source,
  salary_basis,
  count(*) AS postings,
  approx_percentile(salary_annual_min, 0.5) AS median_annual_min,
  approx_percentile(salary_annual_max, 0.5) AS median_annual_max
FROM latest
WHERE rn = 1
  AND NOT salary_is_predicted
  AND salary_annual_min IS NOT NULL
GROUP BY source, salary_basis
ORDER BY source, salary_basis;
