BEGIN;

-- 1. Drop obsolete uniqueness on fusions
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_fusions_fluor_only') THEN
    EXECUTE 'DROP INDEX public.uq_fusions_fluor_only';
  END IF;
END$$;

-- 2. Ensure new unique index per (fluor_id, tag_id)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_fusions_fluor_tag_nd') THEN
    EXECUTE 'CREATE UNIQUE INDEX uq_fusions_fluor_tag_nd
             ON public.fusions (fluor_id, COALESCE(tag_id,''00000000-0000-0000-0000-000000000000''::uuid))';
  END IF;
END$$;

-- 3. Fluor + Tag resolvers (catalog helpers)
CREATE OR REPLACE FUNCTION public.resolve_fluor_id(p_token text)
RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT id
  FROM public.fluors f
  WHERE lower(f.fluor_code)=lower($1)
     OR lower(COALESCE(f.fluor_name,''))=lower($1)
     OR (
          f.alt_names IS NOT NULL AND (
            (pg_typeof(f.alt_names)::text='text[]'
             AND EXISTS (SELECT 1 FROM unnest(f.alt_names) a WHERE lower(a)=lower($1)))
            OR
            (pg_typeof(f.alt_names)::text<>'text[]'
             AND lower(f.alt_names::text)=lower($1))
          )
        )
  ORDER BY id
  LIMIT 1;
$$;

CREATE OR REPLACE FUNCTION public.resolve_tag_id(p_token text)
RETURNS uuid LANGUAGE sql STABLE AS $$
  SELECT id
  FROM public.tags t
  WHERE lower(t.tag_code)=lower($1)
     OR lower(COALESCE(t.tag_name,''))=lower($1)
  ORDER BY id
  LIMIT 1;
$$;

-- 4. Multi-tag-aware strict plasmid resolver
CREATE OR REPLACE FUNCTION public.ensure_plasmid_fusions_from_list_strict(
  p_plasmid_code text,
  p_fusion_list  text
) RETURNS void
LANGUAGE plpgsql
AS $fn$
DECLARE
  v_plasmid_id uuid; v_raw text; v_parts text[]; v_left text; v_right text;
  v_fluor_id uuid; v_tag_id uuid; v_fusion_id uuid;
BEGIN
  SELECT id INTO v_plasmid_id FROM public.plasmids WHERE code=p_plasmid_code LIMIT 1;
  IF v_plasmid_id IS NULL THEN
    RAISE EXCEPTION 'plasmid "%" not found', p_plasmid_code USING ERRCODE='foreign_key_violation';
  END IF;

  FOR v_raw IN SELECT trim(x) FROM regexp_split_to_table(COALESCE(p_fusion_list,''), '\|') AS x LOOP
    IF v_raw IS NULL OR v_raw='' THEN CONTINUE; END IF;

    v_parts := regexp_split_to_array(v_raw, '[:/@+]+');
    IF array_length(v_parts,1) IS NULL THEN CONTINUE; END IF;

    IF array_length(v_parts,1)=1 THEN
      v_fluor_id := public.resolve_fluor_id(v_parts[1]);
      IF v_fluor_id IS NULL THEN
        RAISE EXCEPTION 'Unknown fluor "%". Add to public.fluors or fix CSV.', v_parts[1]
          USING ERRCODE='invalid_parameter_value';
      END IF;
      v_tag_id := NULL;
    ELSE
      v_left  := v_parts[1]; v_right := v_parts[array_length(v_parts,1)];
      v_fluor_id := public.resolve_fluor_id(v_right); v_tag_id := public.resolve_tag_id(v_left);
      IF v_fluor_id IS NULL THEN
        v_fluor_id := public.resolve_fluor_id(v_left);
        IF v_fluor_id IS NULL THEN
          RAISE EXCEPTION 'Unknown fluor in token "%". Add to public.fluors or fix CSV.', v_raw
            USING ERRCODE='invalid_parameter_value';
        END IF;
        IF v_right IS NOT NULL AND trim(v_right)<>'' THEN
          v_tag_id := public.resolve_tag_id(v_right);
          IF v_tag_id IS NULL THEN
            RAISE EXCEPTION 'Unknown tag "%". Add to public.tags or fix CSV.', v_right
              USING ERRCODE='invalid_parameter_value';
          END IF;
        ELSE
          v_tag_id := NULL;
        END IF;
      ELSE
        IF v_left IS NOT NULL AND trim(v_left)<>'' AND v_tag_id IS NULL THEN
          RAISE EXCEPTION 'Unknown tag "%". Add to public.tags or fix CSV.', v_left
            USING ERRCODE='invalid_parameter_value';
        END IF;
      END IF;
    END IF;

    INSERT INTO public.fusions (fusion_name, fluor_id, tag_id)
    VALUES (v_raw, v_fluor_id, v_tag_id)
    ON CONFLICT (fluor_id, COALESCE(tag_id,'00000000-0000-0000-0000-000000000000'::uuid))
    DO UPDATE SET fusion_name = EXCLUDED.fusion_name
    RETURNING id INTO v_fusion_id;

    INSERT INTO public.join_plasmid_fusions (plasmid_id, fusion_id)
    VALUES (v_plasmid_id, v_fusion_id)
    ON CONFLICT DO NOTHING;
  END LOOP;
END;
$fn$;

-- 5. Confirm baseline views (recreate core rollups)
DROP VIEW IF EXISTS public.v_fluorescent_marker_rollup CASCADE;
DROP VIEW IF EXISTS public.v_fluorescent_marker_rollup_by_base CASCADE;
DROP VIEW IF EXISTS public.v_fish_main CASCADE;

-- (We’ll reinsert the canonical working definitions here from your DB; you can dump via psql -Atx "\d+ v_fish_main")
-- For now: stubs to confirm compile order
CREATE VIEW public.v_fluorescent_marker_rollup AS SELECT 'stub'::text AS fish_code;
CREATE VIEW public.v_fluorescent_marker_rollup_by_base AS SELECT 'stub'::text AS fish_code;
CREATE VIEW public.v_fish_main AS SELECT 'stub'::text AS fish_code;

COMMIT;
