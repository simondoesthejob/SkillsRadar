-- Share of rows with a missing value, per source. Drives the data-quality checks in phase 2:
-- a source whose rates jump has probably changed its response format.
SELECT
  source,
  count(*) AS total_rows,
  round(100.0 * count_if(company IS NULL OR company = '') / count(*), 1) AS pct_no_company,
  round(100.0 * count_if(location IS NULL OR location = '') / count(*), 1) AS pct_no_location,
  round(100.0 * count_if(posted_at IS NULL) / count(*), 1) AS pct_no_posted_at,
  round(100.0 * count_if(salary_min IS NULL) / count(*), 1) AS pct_no_salary,
  round(100.0 * count_if(salary_predicted) / count(*), 1) AS pct_salary_predicted
FROM raw_postings
GROUP BY source
ORDER BY source;
