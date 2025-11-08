BEGIN;

-- Fish-level FT-based rollup WITH a stub/real 'markers' column for UI compatibility.
-- This mirrors your current FT-based fluors/tags aggregation and adds 'markers' so pages don't break.

CREATE OR REPLACE VIEW public.v_fluorescent_marker_rollup AS
WITH base AS (
  SELECT f.fish_code, jft.ft_code, ftp.fluor_code, ftp.tag_code
  FROM public.join_fish_fluorescent_treatments jft
  JOIN public.fish f          ON f.id = jft.fish_id
  JOIN public.ft_proteins ftp ON ftp.ft_code = jft.ft_code
),
canon AS (
  SELECT
    b.fish_code,
    COALESCE(fl.fluor_code, upper(b.fluor_code)) AS fluor_code,
    COALESCE(tg.tag_code, b.tag_code)            AS tag_code
  FROM base b
  LEFT JOIN public.fluors fl
    ON lower(fl.fluor_code)=lower(b.fluor_code)
     OR lower(COALESCE(fl.fluor_name,''))=lower(b.fluor_code)
  LEFT JOIN public.tags tg
    ON lower(tg.tag_code)=lower(COALESCE(b.tag_code,''))
     OR lower(COALESCE(tg.tag_name,''))=lower(COALESCE(b.tag_code,''))
),
agg AS (
  SELECT
    fish_code,
    COALESCE(string_agg(DISTINCT fluor_code, ',' ORDER BY fluor_code),'')            AS fluors,
    COALESCE(string_agg(DISTINCT COALESCE(tag_code,''), ',' ORDER BY COALESCE(tag_code,'')),'') AS tags
  FROM canon
  GROUP BY fish_code
)
SELECT f.fish_code,
       ''::text              AS markers,   -- compatibility for existing UI
       COALESCE(a.fluors,'') AS fluors,
       COALESCE(a.tags,'')   AS tags,
       ''::text              AS dyes
FROM public.fish f
LEFT JOIN agg a ON a.fish_code=f.fish_code;

COMMIT;
