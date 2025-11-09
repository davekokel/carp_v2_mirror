BEGIN;

CREATE OR REPLACE FUNCTION public.resolve_fusion_id(_combo text)
RETURNS uuid
LANGUAGE plpgsql AS $$
DECLARE
  s text;
  arr text[];
  f_tok text;
  t_tok text;
  v_fluor_id uuid;
  v_tag_id   uuid;
  v_id       uuid;
BEGIN
  IF _combo IS NULL OR btrim(_combo) = '' THEN
    RETURN NULL;
  END IF;

  -- Normalize any of :: : / @ + to '::'
  s := regexp_replace(_combo, '::|:|/|@|\\+', '::', 'g');

  arr := regexp_split_to_array(s, '::');
  f_tok := btrim(arr[1]);
  IF array_length(arr,1) >= 2 THEN
    t_tok := NULLIF(btrim(arr[2]),'');
  ELSE
    t_tok := NULL;
  END IF;

  SELECT public.resolve_fluor_id(f_tok), public.resolve_tag_id(t_tok)
    INTO v_fluor_id, v_tag_id;

  IF v_fluor_id IS NULL AND v_tag_id IS NULL THEN
    RETURN NULL;
  END IF;

  SELECT id INTO v_id
  FROM public.fusions
  WHERE fluor_id IS NOT DISTINCT FROM v_fluor_id
    AND tag_id   IS NOT DISTINCT FROM v_tag_id;

  IF v_id IS NOT NULL THEN
    RETURN v_id;
  END IF;

  INSERT INTO public.fusions(fluor_id, tag_id)
  VALUES (v_fluor_id, v_tag_id)
  ON CONFLICT (fluor_id, tag_id) DO UPDATE SET tag_id = EXCLUDED.tag_id
  RETURNING id INTO v_id;

  RETURN v_id;
END $$;

COMMIT;
