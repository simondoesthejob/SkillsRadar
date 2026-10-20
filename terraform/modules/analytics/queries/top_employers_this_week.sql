-- Employers with the most distinct postings over the last 7 days, across all sources.
-- Recruitment agencies often dominate this list; that is a finding worth noting on the
-- methodology page.
SELECT
  company,
  count(DISTINCT dedupe_key) AS postings,
  count(DISTINCT source) AS sources
FROM raw_postings
WHERE dt >= date_format(date_add('day', -7, current_date), '%Y-%m-%d')
  AND company IS NOT NULL
  AND company <> ''
GROUP BY company
ORDER BY postings DESC
LIMIT 25;
