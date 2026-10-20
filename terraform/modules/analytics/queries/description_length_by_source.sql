-- Description length in characters, per source. Reed search results carry truncated text, so
-- its numbers should be much lower than Adzuna's or Hacker News's; the gap is the reason the
-- Reed enrichment step (full description per job) exists.
SELECT
  source,
  count(*) AS total_rows,
  min(length(description)) AS min_chars,
  approx_percentile(length(description), 0.5) AS median_chars,
  approx_percentile(length(description), 0.9) AS p90_chars,
  max(length(description)) AS max_chars
FROM raw_postings
GROUP BY source
ORDER BY source;
