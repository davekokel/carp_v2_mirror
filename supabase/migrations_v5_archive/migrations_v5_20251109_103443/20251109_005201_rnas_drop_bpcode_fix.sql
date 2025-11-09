BEGIN;

-- 1) Drop any views that depend on rnas.base_plasmid_code
DROP VIEW IF EXISTS public.v_rnas;

-- 2) Drop the column(s) now that dependencies are gone
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='rnas' AND column_name='base_plasmid_code'
  ) THEN
    ALTER TABLE public.rnas DROP COLUMN base_plasmid_code;
  END IF;

  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='rnas' AND column_name='genetic_element'
  ) THEN
    ALTER TABLE public.rnas DROP COLUMN genetic_element;
  END IF;
END$$;

-- 3) Recreate v_rnas without base_plasmid_code
CREATE VIEW public.v_rnas AS
SELECT
  r.id        AS rna_id,
  r.rna_code  AS rna_code,
  r.created_at,
  COALESCE(
    string_agg(DISTINCT fl.fluor_code, ', ' ORDER BY fl.fluor_code)
      FILTER (WHERE fl.id IS NOT NULL),''
  ) AS fluors,
  COALESCE(
    string_agg(DISTINCT tg.tag_code,  ', ' ORDER BY tg.tag_code)
      FILTER (WHERE tg.id IS NOT NULL),''
  ) AS tags
FROM public.rnas r
LEFT JOIN public.join_rna_fusions jrf ON jrf.rna_id = r.id
LEFT JOIN public.fusions fu           ON fu.id      = jrf.fusion_id
LEFT JOIN public.fluors  fl           ON fl.id      = fu.fluor_id
LEFT JOIN public.tags    tg           ON tg.id      = fu.tag_id
GROUP BY r.id, r.rna_code, r.created_at;

COMMIT;
