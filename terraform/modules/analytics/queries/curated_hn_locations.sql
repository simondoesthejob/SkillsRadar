-- Locations found by the Hacker News header parser, with how many of those posts are remote.
-- Hacker News is tech-heavy and not UK-specific, so treat it as a development dataset. The
-- header parse is a heuristic; check the top rows for things that are not places.
WITH latest AS (
  SELECT
    *,
    row_number() OVER (PARTITION BY dedupe_key ORDER BY dt DESC) AS rn
  FROM curated_postings
  WHERE source = 'hn_hiring'
)
SELECT
  location,
  count(*) AS postings,
  count_if(remote) AS remote_postings
FROM latest
WHERE rn = 1
  AND location IS NOT NULL
GROUP BY location
ORDER BY postings DESC
LIMIT 30;
