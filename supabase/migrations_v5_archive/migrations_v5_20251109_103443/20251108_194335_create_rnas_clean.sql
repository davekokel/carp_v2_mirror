BEGIN;

-- rnas table (safe if already present)
CREATE TABLE IF NOT EXISTS public.rnas (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  rna_code text UNIQUE NOT NULL,
  base_plasmid_code text NULL,
  created_at timestamptz DEFAULT now()
);

-- helper index (if you look up by code)
CREATE INDEX IF NOT EXISTS idx_rnas_code ON public.rnas(rna_code);

-- Modern v_rnas: roll up the fusions an RNA expresses via join_rna_fusions → fusions → (fluors, tags)
DROP VIEW IF EXISTS public.v_rnas;
CREATE VIEW public.v_rnas AS
SELECT
  r.id         AS rna_id,
  r.rna_code   AS rna_code,
  r.base_plasmid_code,
  r.created_at,
  COALESCE(
    string_agg(DISTINCT fl.fluor_code, ', ' ORDER BY fl.fluor_code)
      FILTER (WHERE fl.id IS NOT NULL), ''
  ) AS fluors,
  COALESCE(
    string_agg(DISTINCT tg.tag_code, ', ' ORDER BY tg.tag_code)
      FILTER (WHERE tg.id IS NOT NULL), ''
  ) AS tags
FROM public.rnas r
LEFT JOIN public.join_rna_fusions jrf ON jrf.rna_id = r.id
LEFT JOIN public.fusions fu           ON fu.id      = jrf.fusion_id
LEFT JOIN public.fluors  fl           ON fl.id      = fu.fluor_id
LEFT JOIN public.tags    tg           ON tg.id      = fu.tag_id
GROUP BY r.id, r.rna_code, r.base_plasmid_code, r.created_at;

COMMIT;
