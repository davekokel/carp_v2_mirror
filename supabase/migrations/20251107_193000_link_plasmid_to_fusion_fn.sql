BEGIN;

CREATE OR REPLACE FUNCTION public.link_plasmid_to_fusion(p_plasmid_code text, p_fusion_name text)
RETURNS void
LANGUAGE plpgsql
AS $$
DECLARE
  parts text[];
  p1 text;
  p2 text;
  v_fluor_id uuid;
  v_tag_id   uuid;
  v_plasmid_id uuid;
  v_fusion_id  uuid;
  v_fluor_name text;
  v_tag_name   text;
  v_fusion_code text;
BEGIN
  IF p_plasmid_code IS NULL OR btrim(p_plasmid_code) = '' THEN
    RAISE EXCEPTION 'plasmid_code is required';
  END IF;
  IF p_fusion_name IS NULL OR btrim(p_fusion_name) = '' THEN
    RAISE EXCEPTION 'fusion_name is required (expected "tag::fluor" or "fluor::tag") for plasmid %', p_plasmid_code;
  END IF;

  parts := regexp_split_to_array(btrim(p_fusion_name), '\s*::\s*');
  IF array_length(parts,1) <> 2 THEN
    RAISE EXCEPTION 'fusion_name must be exactly two parts separated by "::" (got: %)', p_fusion_name;
  END IF;

  p1 := btrim(parts[1]);
  p2 := btrim(parts[2]);

  SELECT id, fluor_name INTO v_fluor_id, v_fluor_name
  FROM public.fluors
  WHERE lower(fluor_name)=lower(p1) OR lower(coalesce(fluor_code,''))=lower(p1)
  LIMIT 1;

  SELECT id, tag_name INTO v_tag_id, v_tag_name
  FROM public.tags
  WHERE lower(tag_name)=lower(p2) OR lower(coalesce(tag_code,''))=lower(p2)
  LIMIT 1;

  IF v_fluor_id IS NULL OR v_tag_id IS NULL THEN
    -- try the opposite order
    SELECT id, fluor_name INTO v_fluor_id, v_fluor_name
    FROM public.fluors
    WHERE lower(fluor_name)=lower(p2) OR lower(coalesce(fluor_code,''))=lower(p2)
    LIMIT 1;

    SELECT id, tag_name INTO v_tag_id, v_tag_name
    FROM public.tags
    WHERE lower(tag_name)=lower(p1) OR lower(coalesce(tag_code,''))=lower(p1)
    LIMIT 1;
  END IF;

  IF v_fluor_id IS NULL OR v_tag_id IS NULL THEN
    RAISE EXCEPTION 'could not resolve fusion_name % to a fluor and tag (plasmid %)', p_fusion_name, p_plasmid_code;
  END IF;

  SELECT id INTO v_plasmid_id FROM public.plasmids WHERE code = p_plasmid_code LIMIT 1;
  IF v_plasmid_id IS NULL THEN
    RAISE EXCEPTION 'unknown plasmid_code: %', p_plasmid_code;
  END IF;

  v_fusion_code := replace(lower(v_fluor_name), ' ', '') || '-' || replace(lower(v_tag_name),' ',''); -- stable code
  INSERT INTO public.fusions (fusion_code, fusion_name, fluor_id, tag_id)
  VALUES (v_fusion_code, v_fluor_name || '::' || v_tag_name, v_fluor_id, v_tag_id)
  ON CONFLICT (fusion_code) DO UPDATE
    SET fluor_id = EXCLUDED.fluor_id,
        tag_id   = EXCLUDED.tag_id
  RETURNING id INTO v_fusion_id;

  INSERT INTO public.join_plasmid_fusions(plasmid_id, fusion_id)
  VALUES (v_plasmid_id, v_fusion_id)
  ON CONFLICT DO NOTHING;
END;
$$;

COMMIT;
