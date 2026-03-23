RECO_SQL = """
WITH input AS (
  SELECT ARRAY(SELECT DISTINCT x FROM unnest(%s::int[]) x ORDER BY x) AS in_arr
),
bkeys AS (
  SELECT DISTINCT
    b_key,
    string_to_array(b_key, '-')::int[] AS b_arr
  FROM matchup_summary
  WHERE match_id = %s
),
scored AS (
  SELECT
    bk.b_key,
    (SELECT COUNT(*)
     FROM unnest(bk.b_arr) x
     JOIN unnest(i.in_arr) y ON x = y
    ) AS overlap,
    cardinality(i.in_arr) AS input_n,
    (SELECT COALESCE(SUM(total_seconds),0)
     FROM matchup_summary ms
     WHERE ms.match_id = %s AND ms.b_key = bk.b_key
    ) AS seconds_total
  FROM bkeys bk
  CROSS JOIN input i
),
chosen AS (
  SELECT b_key, overlap, input_n, seconds_total
  FROM scored
  ORDER BY overlap DESC, seconds_total DESC
  LIMIT 1
),
filtered AS (
  SELECT
    ms.*,
    c.overlap AS chosen_overlap,
    c.input_n AS input_n
  FROM matchup_summary ms
  JOIN chosen c ON ms.b_key = c.b_key
  WHERE ms.match_id = %s
    AND ms.total_seconds >= %s
),
greens AS (
  SELECT DISTINCT ON (a_key)
    'GREEN' AS flag, b_key, a_key, total_seconds, total_diff, diff_per_min, chosen_overlap, input_n
  FROM filtered
  ORDER BY a_key, diff_per_min DESC, total_seconds DESC
),
top_greens AS (
  SELECT *
  FROM greens
  ORDER BY diff_per_min DESC, total_seconds DESC
  LIMIT 3
),
reds AS (
  SELECT DISTINCT ON (a_key)
    'RED' AS flag, b_key, a_key, total_seconds, total_diff, diff_per_min, chosen_overlap, input_n
  FROM filtered
  ORDER BY a_key, diff_per_min ASC, total_seconds DESC
),
top_red AS (
  SELECT r.*
  FROM reds r
  WHERE NOT EXISTS (
    SELECT 1 FROM top_greens g
    WHERE g.a_key = r.a_key
  )
  ORDER BY r.diff_per_min ASC, r.total_seconds DESC
  LIMIT 1
),
final AS (
  SELECT 0 AS sort_key, * FROM top_greens
  UNION ALL
  SELECT 1 AS sort_key, * FROM top_red
)
SELECT
  flag, b_key, a_key, total_seconds, total_diff, diff_per_min, chosen_overlap, input_n
FROM final
ORDER BY sort_key ASC, diff_per_min DESC;
"""

OPP_STRONGEST_B_SQL = """
WITH agg AS (
  SELECT
    b_key,
    SUM(total_seconds) AS seconds_total,
    SUM(total_diff)    AS diff_total
  FROM matchup_summary
  WHERE match_id = %s
  GROUP BY b_key
)
SELECT
  b_key,
  seconds_total,
  diff_total,
  (diff_total / NULLIF(seconds_total,0)) * 60.0 AS diff_per_min
FROM agg
WHERE seconds_total >= %s
ORDER BY diff_total ASC, seconds_total DESC
LIMIT 1;
"""

VS_B_RESPONSES_SQL = """
SELECT
  a_key,
  total_seconds,
  total_diff,
  diff_per_min
FROM matchup_summary
WHERE match_id = %s
  AND b_key = %s
  AND total_seconds >= %s
ORDER BY diff_per_min DESC, total_seconds DESC;
"""

TOP_B_OVERVIEW_SQL = """
WITH agg AS (
  SELECT
    b_key,
    SUM(total_seconds) AS seconds_total,
    SUM(total_diff)    AS diff_total
  FROM matchup_summary
  WHERE match_id = %s
  GROUP BY b_key
)
SELECT
  b_key,
  seconds_total,
  diff_total,
  (diff_total / NULLIF(seconds_total,0)) * 60.0 AS diff_per_min
FROM agg
WHERE seconds_total >= %s
ORDER BY diff_total ASC, seconds_total DESC
LIMIT 10;
"""
ALL_B_AGG_SQL = """
WITH agg AS (
  SELECT
    b_key,
    SUM(total_seconds) AS seconds_total,
    SUM(total_diff)    AS diff_total
  FROM matchup_summary
  WHERE match_id = %s
  GROUP BY b_key
)
SELECT
  b_key,
  seconds_total,
  diff_total,
  (diff_total / NULLIF(seconds_total,0)) * 60.0 AS diff_per_min
FROM agg
WHERE seconds_total >= %s
ORDER BY diff_total ASC, seconds_total DESC;
"""
BEST_A_OVERALL_SQL = """
WITH agg AS (
  SELECT
    a_key,
    SUM(total_seconds) AS seconds_total,
    SUM(total_diff)    AS diff_total
  FROM matchup_summary
  WHERE match_id = %s
  GROUP BY a_key
)
SELECT
  a_key,
  seconds_total,
  diff_total,
  (diff_total / NULLIF(seconds_total,0)) * 60.0 AS diff_per_min
FROM agg
WHERE seconds_total >= %s
ORDER BY diff_total DESC, seconds_total DESC
LIMIT %s;
"""