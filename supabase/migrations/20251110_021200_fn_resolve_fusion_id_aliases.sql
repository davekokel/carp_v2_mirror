BEGIN;
CREATE OR REPLACE FUNCTION public.resolve_fusion_id(_combo text)
RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE f_tok text; t_tok text; v_fluor_id uuid; v_tag_id uuid; v_id uuid;
BEGIN
  IF _combo IS NULL OR btrim(_combo) = '' THEN RETURN NULL; END IF;

  IF position('::' IN _combo) > 0 OR position(':' IN _combo) > 0
     OR position('/' IN _combo) > 0 OR position('@' IN _combo) > 0
     OR position('+' IN _combo) > 0 THEN
    -- split on the first separator we find
    f_tok := regexp_split_to_array(_combo, '::|:|/|@|\\+')[1];
    t_tok := regexp_split_to_array(_combo, '::|:|/|@|\\+')[2];
  ELSE
    f_tok := _combo;
    t_tok := NULL;
  END IF;

  SELECT public.resolve_fluor_id(f_tok), public.resolve_tag_id(t_tok)
    INTO v_fluor_id, v_tag_id;

  IF v_tag_id IS NULL AND v_fluor_id IS NULL THEN RETURN NULL; END IF;

  SELECT id INTO v_id FROM public.fusions
   WHERE fluor_id IS NOT DISTINCT FROM v_fluor_id AND tag_id IS NOT DISTINCT FROM v_tag_id;
  IF v_id IS NOT NULL THEN RETURN v_id; END IF;

  INSERT INTO public.fusions(fluor_id, tag_id)
  VALUES (v_fluor_id, v_tag_id)
  ON CONFLICT (fluor_id, tag_id) DO UPDATE SET tag_id=EXCLUDED.tag_id
  RETURNING id INTO v_id;
  RETURN v_id;
END $$;
COMMIT;
