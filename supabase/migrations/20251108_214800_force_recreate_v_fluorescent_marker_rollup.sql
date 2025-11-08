BEGIN;

-- Roll up markers from FT links (jft + ft_proteins/ft_dyes), not legacy plasmid/fusions.
DROP VIEW IF EXISTS public.v_fluorescent_marker_rollup;

CREATE VIEW public.v_fluorescent_marker_rollup AS
WITH j AS (
  SELECT f.fish_code, jft.ft_code
  FROM public.join_fish_fluorescent_treatments jft
  JOIN public.fish f ON f.id = jft.fish_id
),
prot AS (
  SELECT j.fish_code,
         fp.fluor_code,
         fp.tag_code,
         (fp.fluor_code||'('||COALESCE(fp.tag_code,'')||')') AS marker
  FROM j
  JOIN public.ft_proteins fp ON fp.ft_code = j.ft_code
),
dyes AS (
  SELECT j.fish_code, fd.dye_code
  FROM j
  JOIN public.ft_dyes fd ON fd.ft_code = j.ft_code
),
agg AS (
  SELECT fish_code,
         string_agg(DISTINCT marker, ',' ORDER BY marker)           AS markers,
         string_agg(DISTINCT fluor_code, ',' ORDER BY fluor_code)   AS fluors,
         string_agg(DISTINCT tag_code, ',' ORDER BY tag_code)       AS tags
  FROM prot
  GROUP BY fish_code
),
agg_dyes AS (
  SELECT fish_code,
         string_agg(DISTINCT dye_code, ',' ORDER BY dye_code) AS dyes
  FROM dyes
  GROUP BY fish_code
)
SELECT f.fish_code,
       COALESCE(a.markers,'') AS markers,
       COALESCE(a.fluors,'')  AS fluors,
       COALESCE(a.tags,'')    AS tags,
       COALESCE(d.dyes,'')    AS dyes
FROM public.fish f
LEFT JOIN agg a      ON a.fish_code = f.fish_code
LEFT JOIN agg_dyes d ON d.fish_code = f.fish_code;

COMMIT;
