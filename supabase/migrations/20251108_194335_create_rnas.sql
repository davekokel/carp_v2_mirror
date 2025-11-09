BEGIN;

CREATE TABLE IF NOT EXISTS public.rnas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rna_code text UNIQUE NOT NULL,
  rna_name text,
  base_plasmid_code text NOT NULL REFERENCES public.plasmids(code) ON UPDATE CASCADE ON DELETE RESTRICT,
  genetic_element text,
  notes text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS ix_rnas_base_plasmid_code ON public.rnas(base_plasmid_code);

CREATE OR REPLACE VIEW public.v_rnas AS
WITH p AS (
  SELECT
    r.id,
    r.rna_code,
    r.rna_name,
    r.base_plasmid_code,
    r.genetic_element,
    r.notes,
    r.created_by,
    r.created_at,
    pz.name AS base_plasmid_name
  FROM public.rnas r
  LEFT JOIN public.plasmids pz ON pz.code = r.base_plasmid_code
),
ctx AS (
  SELECT
    p.base_plasmid_code,
    COALESCE(string_agg(DISTINCT f.fusion_name, ', ' ORDER BY f.fusion_name), '') AS fusion_names,
    COALESCE(string_agg(DISTINCT COALESCE(fl.fluor_name, fl.fluor_code), ', ' ORDER BY COALESCE(fl.fluor_name, fl.fluor_code)), '') AS fluor_names,
    COALESCE(string_agg(DISTINCT COALESCE(tg.tag_name, tg.tag_code), ', ' ORDER BY COALESCE(tg.tag_name, tg.tag_code)), '') AS tag_names
  FROM public.plasmids p
  LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
  LEFT JOIN public.fusions f ON f.id = jpf.fusion_id
  LEFT JOIN public.fluors fl ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg ON tg.id = f.tag_id
  GROUP BY p.base_plasmid_code
)
SELECT
  p.id,
  p.rna_code,
  p.rna_name,
  p.base_plasmid_code,
  p.base_plasmid_name,
  p.genetic_element,
  COALESCE(ctx.fusion_names,'') AS fusion_names,
  COALESCE(ctx.fluor_names,'')  AS fluor_names,
  COALESCE(ctx.tag_names,'')    AS tag_names,
  COALESCE(p.notes,'')          AS notes,
  p.created_by,
  p.created_at
FROM p
LEFT JOIN ctx ON ctx.base_plasmid_code = p.base_plasmid_code
ORDER BY p.rna_code;

COMMIT;
