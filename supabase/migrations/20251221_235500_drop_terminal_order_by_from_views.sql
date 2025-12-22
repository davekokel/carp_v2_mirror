BEGIN;

CREATE OR REPLACE FUNCTION public._strip_terminal_order_by(def text)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  i int;
  n int;
  depth int := 0;
  in_str boolean := false;
  c text;
  nxt text;
  needle text := 'order by';
  last_pos int := 0;
BEGIN
  IF def IS NULL OR length(def) < 8 THEN
    RETURN def;
  END IF;

  n := length(def);
  i := 1;
  WHILE i <= n LOOP
    c := substr(def, i, 1);

    IF in_str THEN
      IF c = '''' THEN
        IF i < n AND substr(def, i+1, 1) = '''' THEN
          i := i + 2;
          CONTINUE;
        ELSE
          in_str := false;
        END IF;
      END IF;
      i := i + 1;
      CONTINUE;
    ELSE
      IF c = '''' THEN
        in_str := true;
        i := i + 1;
        CONTINUE;
      END IF;

      IF c = '(' THEN
        depth := depth + 1;
      ELSIF c = ')' THEN
        IF depth > 0 THEN
          depth := depth - 1;
        END IF;
      END IF;

      IF depth = 0 AND i <= n-7 THEN
        IF lower(substr(def, i, 8)) = needle THEN
          last_pos := i;
        END IF;
      END IF;

      i := i + 1;
    END IF;
  END LOOP;

  IF last_pos = 0 THEN
    RETURN regexp_replace(def, E';\\s*$', '');
  END IF;

  RETURN regexp_replace(rtrim(substr(def, 1, last_pos-1)), E';\\s*$', '');
END $$;

DO $$
DECLARE
  vname text;
  def text;
  newdef text;
BEGIN
  FOREACH vname IN ARRAY ARRAY[
    'v_construct_marker_styles',
    'v_genotype_marker_styles_strict',
    'v_roi_overview',
    'v_roi_overview_display_v6',
    'v_transgenes_overview',
    'v11_clutch_allele_marker_style',
    'v11_clutch_flat_overview',
    'v11_clutch_label_star',
    'v11_clutch_selection_star',
    'v11_clutch_star',
    'v11_clutch_treated_groups_flat',
    'v11_fish_allele_rollups',
    'v11_fish_construct_rollups',
    'v11_fish_group_star',
    'v11_fish_instance_star',
    'v11_fish_instance_star_labels',
    'v11_fish_line_star',
    'v11_fish_marker_rollups',
    'v11_imaging_clutch_parent_star',
    'v11_line_allele_rollups',
    'v11_treated_clutch_genotype_star',
    'v11_treatment_label_star',
    'v11_treatment_star'
  ]
  LOOP
    SELECT pg_get_viewdef(('public.'||vname)::regclass, true) INTO def;
    IF def IS NULL THEN
      RAISE EXCEPTION '[STOP] missing viewdef for %', vname;
    END IF;

    newdef := public._strip_terminal_order_by(def);
    EXECUTE format('CREATE OR REPLACE VIEW public.%I AS %s', vname, newdef);
  END LOOP;
END $$;

DROP FUNCTION public._strip_terminal_order_by(text);

COMMIT;
