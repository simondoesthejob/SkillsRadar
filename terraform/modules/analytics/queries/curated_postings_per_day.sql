-- Curated rows per source per day (last 14 days): how many distinct postings were seen, how many
-- raw rows they came from, and how many descriptions are truncated by the source API.
SELECT
  dt,
  source,
  count(*) AS postings,
  sum(observed_count) AS raw_rows,
  count_if(description_truncated) AS truncated_descriptions
FROM curated_postings
WHERE dt >= date_format(date_add('day', -14, current_date), '%Y-%m-%d')
GROUP BY dt, source
ORDER BY dt DESC, source;
