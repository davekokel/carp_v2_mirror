BEGIN;

-- Upsert a fusion by names/codes; resolve to IDs; return fusion_id
CREATE OR REPLACE FUNCTION public.upsert_fusion_by_names(p_fusion_name text, p_fluor text, p_tag text DEFAULT NULL)
RETURNS uuid
LANGUAGE plpgsql
AS $$
DECLARE
  v_fluor_id uuid;
  v_tag_id   uuid;
  v_fusion_id uuid;
BEGIN
  -- Resolve fluor by code OR name
  SELECT id INTO v_fluor_id
  FROM public.fluors
  WHERE fluor_code = p_fluor OR fluor_name = p_fluor
  LIMIT 1;

  -- Resolve tag by code OR name (nullable)
  IF p_tag IS NOT NULL AND NULLIF(p_tag,'') IS NOT NULL THEN
    SELECT id INTO v_tag_id
    FROM public.tags
    WHERE tag_code = p_tag OR tag_name = p_tag
    LIMIT 1;
  END IF;

  -- Create or reuse a fusion row keyed by (fusion_name, fluor_id, tag_id)
  INSERT INTO public.fusions (fusion_name, fluor_id, tag_id)
  VALUES (p_fusion_name, v_fluor_id, v_tag_id)
  ON CONFLICT (fusion_name, COALESCE(fluor_id, '00000000-0000-0000-0000-000000000000'::uuid), COALESCE(tag_id, '00000000-0000-0000-0000-000000000000'::uuid))
  DO UPDATE SET fusion_name = EXCLUDED.fusion_name
  RETURNING id INTO v_fusion_id;

  RETURN v_fusion_id;
END;
$$;

-- Given a plasmid code and a pipe-delimited list like 'mScarlet|mKate2|Electra2',
-- create join_plasmid_fusions rows with resolved fluor/tag IDs.
CREATE OR REPLACE FUNCTION public.ensure_plasmid_fusions_from_list(p_plasmid_code text, p_fusion_list text)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  v_plasmid_id uuid;
  v_part text;
  v_fusion_id uuid;
BEGIN
  SELECT id INTO v_plasmid_id FROM public.plasmids WHERE code = p_plasmid_code LIMIT 1;
  IF v_plasmid_id IS NULL THEN
    RAISE NOTICE 'plasmid % not found', p_plasmid_code;
    RETURN;
  END IF;

  FOR v_part IN
    SELECT trim(x) FROM regexp_split_to_table(COALESCE(p_fusion_list,''), '\|') AS x
  LOOP
    EXIT WHEN v_part IS NULL OR v_part = '';
    -- Treat each token as a fluor name/code (tag is optional/unknown here)
    v_fusion_id := public.upsert_fusion_by_names(v_part, v_part, NULL);

    INSERT INTO public.join_plasmid_fusions (plasmid_id, fusion_id)
    VALUES (v_plasmid_id, v_fusion_id)
    ON CONFLICT DO NOTHING;
  END LOOP;
END;
$$;

COMMIT;
