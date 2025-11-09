BEGIN;
CREATE OR REPLACE FUNCTION public.resolve_fusion_id(_combo text)
RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE f text; t text; v_fluor_id uuid; v_tag_id uuid; v_id uuid;
BEGIN
  IF _combo IS NULL OR btrim(_combo) = '' THEN RETURN NULL; END IF;
  IF position('::' IN _combo) > 0 THEN
    f := split_part(_combo, '::', 1);
    t := split_part(_combo, '::', 2);
  ELSE
    f := _combo;
    t := NULL;
  END IF;
  IF f IS NOT NULL AND f <> '' THEN SELECT id INTO v_fluor_id FROM public.fluors WHERE fluor_code=f; END IF;
  IF t IS NOT NULL AND t <> '' THEN SELECT id INTO v_tag_id FROM public.tags WHERE tag_code=t; END IF;
  IF v_tag_id IS NULL AND v_fluor_id IS NULL THEN RETURN NULL; END IF;
  SELECT id INTO v_id FROM public.fusions WHERE fluor_id IS NOT DISTINCT FROM v_fluor_id AND tag_id IS NOT DISTINCT FROM v_tag_id;
  IF v_id IS NOT NULL THEN RETURN v_id; END IF;
  INSERT INTO public.fusions(fluor_id, tag_id)
  VALUES (v_fluor_id, v_tag_id)
  ON CONFLICT (fluor_id, tag_id) DO UPDATE SET tag_id=EXCLUDED.tag_id
  RETURNING id INTO v_id;
  RETURN v_id;
END $$;
COMMIT;
