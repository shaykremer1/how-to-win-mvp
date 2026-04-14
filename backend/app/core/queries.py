RECO_SQL = """
WITH input_b AS (
    SELECT ARRAY(
        SELECT DISTINCT x
        FROM unnest(%s::int[]) AS x
        ORDER BY x
    ) AS input_players
),
candidate_b AS (
    SELECT
        s.b_lineup_key AS b_key,
        COUNT(DISTINCT p.player) FILTER (
            WHERE p.player = ANY(ib.input_players)
        ) AS chosen_overlap,
        array_length(ib.input_players, 1) AS input_n,
        SUM(s.time_played_seconds) AS seconds_total
    FROM stints s
    CROSS JOIN input_b ib
    CROSS JOIN LATERAL (
        SELECT DISTINCT x::int AS player
        FROM unnest(string_to_array(s.b_lineup_key, '-')) AS x
    ) AS p
    WHERE s.match_id = ANY(%s::int[])
      AND s.b_lineup_key IS NOT NULL
    GROUP BY s.b_lineup_key, ib.input_players
),
best_b AS (
    SELECT *
    FROM candidate_b
    ORDER BY chosen_overlap DESC, seconds_total DESC, b_key
    LIMIT 1
),
filtered AS (
    SELECT
        s.a_lineup_key AS a_key,
        s.b_lineup_key AS b_key,
        SUM(s.time_played_seconds) AS total_seconds,
        SUM(s.diff) AS total_diff,
        bb.chosen_overlap,
        bb.input_n
    FROM stints s
    JOIN best_b bb
      ON s.b_lineup_key = bb.b_key
    WHERE s.match_id = ANY(%s::int[])
      AND NOT EXISTS (
          SELECT 1
          FROM unnest(string_to_array(s.a_lineup_key, '-')::int[]) AS a(player)
          WHERE NOT (a.player = ANY(%s::int[]))
      )
    GROUP BY s.a_lineup_key, s.b_lineup_key, bb.chosen_overlap, bb.input_n
    HAVING SUM(s.time_played_seconds) >= %s
),
scored AS (
    SELECT
        a_key,
        b_key,
        total_seconds,
        total_diff,
        CASE
            WHEN total_seconds > 0 THEN (total_diff::float / total_seconds) * 60.0
            ELSE 0
        END AS diff_per_min,
        chosen_overlap,
        input_n
    FROM filtered
),
ranked AS (
    SELECT
        s.*,
        ROW_NUMBER() OVER (ORDER BY diff_per_min DESC, total_seconds DESC, a_key) AS rn_best,
        ROW_NUMBER() OVER (ORDER BY diff_per_min ASC, total_seconds DESC, a_key) AS rn_worst
    FROM scored s
),
final AS (
    SELECT 0 AS sort_key, 'GREEN'::text AS flag, *
    FROM ranked
    WHERE rn_best <= 3
    UNION ALL
    SELECT 1 AS sort_key, 'RED'::text AS flag, *
    FROM ranked
    WHERE rn_worst = 1
)
SELECT
    flag,
    b_key,
    a_key,
    total_seconds,
    total_diff,
    diff_per_min,
    chosen_overlap,
    input_n
FROM final
ORDER BY sort_key ASC, diff_per_min DESC, total_seconds DESC;
"""


BEST_A_OVERALL_SQL = """
SELECT
    a_lineup_key AS a_key,
    SUM(time_played_seconds) AS seconds_total,
    SUM(diff) AS diff_total,
    CASE
        WHEN SUM(time_played_seconds) > 0
            THEN (SUM(diff)::float / SUM(time_played_seconds)) * 60.0
        ELSE 0
    END AS diff_per_min
FROM stints
WHERE match_id = ANY(%s::int[])
GROUP BY a_lineup_key
HAVING SUM(time_played_seconds) >= %s
ORDER BY diff_per_min DESC, seconds_total DESC, a_key
LIMIT %s;
"""


ALL_B_AGG_SQL = """
SELECT
    b_lineup_key AS b_key,
    SUM(time_played_seconds) AS seconds_total,
    SUM(diff) AS diff_total,
    CASE
        WHEN SUM(time_played_seconds) > 0
            THEN (SUM(diff)::float / SUM(time_played_seconds)) * 60.0
        ELSE 0
    END AS diff_per_min
FROM stints
WHERE match_id = ANY(%s::int[])
GROUP BY b_lineup_key
HAVING SUM(time_played_seconds) >= %s
ORDER BY diff_per_min ASC, seconds_total DESC, b_key;
"""


VS_B_RESPONSES_SQL = """
SELECT
    a_lineup_key AS a_key,
    SUM(time_played_seconds) AS total_seconds,
    SUM(diff) AS total_diff,
    CASE
        WHEN SUM(time_played_seconds) > 0
            THEN (SUM(diff)::float / SUM(time_played_seconds)) * 60.0
        ELSE 0
    END AS diff_per_min
FROM stints
WHERE match_id = ANY(%s::int[])
  AND b_lineup_key = %s
GROUP BY a_lineup_key
HAVING SUM(time_played_seconds) >= %s
ORDER BY diff_per_min DESC, total_seconds DESC, a_key;
"""
