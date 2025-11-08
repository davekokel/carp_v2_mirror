BEGIN;

-- Generate a safe code from a name (never empty)
CREATE OR REPLACE FUNCTION public.slugify_code(p text)
RETURNS text
LANGUAGE sql
IMMUTABLE
RETURNS NULL ON NULL INPUT
AS $$
  SELECT CASE
           WHEN s <> '' THEN s
           ELSE 'fusion_'||substr(md5(coalesce(p,'')),1,8)
         END
  FROM (SELECT trim(both '_' FROM lower(regexp_replace(coalesce(p,''), '[^a-zA-Z0-9]+', '_', 'g')))) t(s);
$$;

-- Ensure future inserts always have fusion_code (forward-only)
CREATE OR REPLACE FUNCTION public.fusions_set_code_before_insert()
RETURNS trigger
LANGUAGE plpgsql
AS $fn$
BEGIN
  IF NEW.fusion_code IS NULL OR NEW.fusion_code = '' THEN
    NEW.fusion_code := public.slugify_code(NEW.fusion_name);
  END IF;
  RETURN NEW;
END;
$fn$;

DROP TRIGGER IF EXISTS trg_fusions_set_code_before_insert ON public.fusions;
CREATE TRIGGER trg_fusions_set_code_before_insert
BEFORE INSERT ON public.fusions
FOR EACH ROW EXECUTE FUNCTION public.fusions_set_code_before_insert();

-- Dedupe key we upsert on (works with NULLS)
CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_name_fluor_tag_nd
  ON public.fusions (fusion_name, fluor_id, tag_id) NULLS NOT DISTINCT;

-- Upsert helper (forward-only; no backfill)
CREATE OR REPLACE FUNCTION public.upsert_fusion_by_names(
  p_fusion_name text,
  p_fluor text,
  p_tag   text DEFAULT NULL
) RETURNS uuid
LANGUAGE plpgsql
AS $fn$
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
    SET fusion_name = EXCLUDED.fusion_name  -- keep code via trigger; no backfill
  RETURNING id INTO v_fusion_id;

  RETURN v_fusion_id;
END;
$fn$;

-- Join dedupe safety (forward-only)
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
