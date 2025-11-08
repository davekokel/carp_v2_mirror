BEGIN;

-- 1) Make (fusion_name, fluor_id, tag_id) a real dedupe key
CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_name_fluor_tag_nd
  ON public.fusions (fusion_name, fluor_id, tag_id) NULLS NOT DISTINCT;

-- 2) Upsert by that key; resolve fluor/tag by code OR name
CREATE OR REPLACE FUNCTION public.upsert_fusion_by_names(
  p_fusion_name text,
  p_fluor text,
  p_tag   text DEFAULT NULL
) RETURNS uuid
LANGUAGE plpgsql AS $fn$
DECLARE
  v_fluor_id  uuid;
  v_tag_id    uuid;
  v_fusion_id uuid;
BEGIN
  SELECT id INTO v_fluor_id
  FROM public.fluors
  WHERE fluor_code = p_fluor OR fluor_name = p_fluor
  LIMIT 1;

  IF p_tag IS NOT NULL AND NULLIF(p_tag,'') IS NOT NULL THEN
    SELECT id INTO v_tag_id
    FROM public.tags
    WHERE tag_code = p_tag OR tag_name = p_tag
    LIMIT 1;
  END IF;

  INSERT INTO public.fusions (fusion_name, fluor_id, tag_id)
  VALUES (p_fusion_name, v_fluor_id, v_tag_id)
  ON CONFLICT (fusion_name, fluor_id, tag_id) DO UPDATE
    SET fusion_name = EXCLUDED.fusion_name
  RETURNING id INTO v_fusion_id;

  RETURN v_fusion_id;
END;
$fn$;

-- 3) (Optional safety) ensure join constraint exists
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND indexname='uq_join_plasmid_fusions_plasmid_fusion'
  ) THEN
    CREATE UNIQUE INDEX uq_join_plasmid_fusions_plasmid_fusion
      ON public.join_plasmid_fusions (plasmid_id, fusion_id);
  END IF;
END$$;

COMMIT;
