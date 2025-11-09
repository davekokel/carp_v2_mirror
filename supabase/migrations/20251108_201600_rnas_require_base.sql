BEGIN;

-- 1) Require a base again (all rows must have it)
ALTER TABLE public.rnas
  ALTER COLUMN base_plasmid_code SET NOT NULL;

-- 2) v_rnas already tolerates/joins base → no change needed if you
--    are on your latest v_rnas. If not sure, recreate it here:

DROP VIEW IF EXISTS public.v_rnas;
CREATE VIEW public.v_rnas AS
WITH r AS (
  SELECT rn.id,
         rn.rna_code,
         COALESCE(NULLIF(rn.rna_name,''), rn.rna_code) AS rna_name,
         rn.base_plasmid_code,
         p.name AS base_plasmid_name,
         rn.genetic_element,
         rn.notes,
         rn.created_by,
         rn.created_at
  FROM public.rnas rn
  LEFT JOIN public.plasmids p ON p.code = rn.base_plasmid_code
),
ctx AS (
  SELECT p.code AS base_plasmid_code,
         COALESCE(string_agg(DISTINCT f.fusion_name, ', ' ORDER BY f.fusion_name),'') AS fusion_names,
         COALESCE(string_agg(DISTINCT fl.fluor_name, ', ' ORDER BY fl.fluor_name),  '') AS fluor_names,
         COALESCE(string_agg(DISTINCT tg.tag_name,   ', ' ORDER BY tg.tag_name),    '') AS tag_names
  FROM public.plasmids p
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
  LEFT JOIN public.fusions f               ON f.id  = jpf.fusion_id
  LEFT JOIN public.fluors  fl              ON fl.id = f.fluor_id
  LEFT JOIN public.tags    tg              ON tg.id = f.tag_id
  GROUP BY p.code
)
SELECT r.id, r.rna_code, r.rna_name, r.base_plasmid_code, r.base_plasmid_name, r.genetic_element,
       COALESCE(ctx.fusion_names,'') AS fusion_names,
       COALESCE(ctx.fluor_names,'')  AS fluor_names,
       COALESCE(ctx.tag_names,'')    AS tag_names,
       COALESCE(r.notes,'')          AS notes,
       r.created_by, r.created_at
FROM r
LEFT JOIN ctx ON ctx.base_plasmid_code = r.base_plasmid_code
ORDER BY r.rna_code;

COMMIT;
