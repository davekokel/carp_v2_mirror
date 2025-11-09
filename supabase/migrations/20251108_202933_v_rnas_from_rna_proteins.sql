BEGIN;

DROP VIEW IF EXISTS public.v_rnas;

CREATE VIEW public.v_rnas AS
WITH rp AS (
  SELECT rna_code,
         lower(fluor_code) AS f_code,
         lower(COALESCE(tag_code,'')) AS t_code
  FROM public.rna_proteins
),
flu AS (
  SELECT lower(fluor_code) AS code,
         COALESCE(NULLIF(fluor_name,''), fluor_code) AS name
  FROM public.fluors
),
tg AS (
  SELECT lower(tag_code) AS code,
         COALESCE(NULLIF(tag_name,''), tag_code) AS name
  FROM public.tags
),
agg AS (
  SELECT rp.rna_code,
         COALESCE(string_agg(DISTINCT flu.name, ', ' ORDER BY flu.name), '') AS fluor_names,
         COALESCE(string_agg(DISTINCT tg.name,  ', ' ORDER BY tg.name),  '') AS tag_names
  FROM rp
  LEFT JOIN flu ON flu.code = rp.f_code
  LEFT JOIN tg  ON tg.code  = rp.t_code
  GROUP BY rp.rna_code
)
SELECT r.id,
       r.rna_code,
       r.rna_name,
       r.base_plasmid_code,
       r.genetic_element,
       COALESCE(agg.fluor_names,'') AS fluor_names,
       COALESCE(agg.tag_names,'')   AS tag_names,
       COALESCE(r.notes,'')         AS notes,
       r.created_by,
       r.created_at
FROM public.rnas r
LEFT JOIN agg ON agg.rna_code = r.rna_code
ORDER BY r.rna_code;

COMMIT;
