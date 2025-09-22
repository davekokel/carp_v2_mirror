DO $$
DECLARE v text;
BEGIN
  -- Only patch if the view exists
  IF to_regclass('public.v_fish_overview_v1') IS NOT NULL THEN
    v := pg_get_viewdef('public.v_fish_overview_v1'::regclass, true);
    -- Replace both fully-qualified and alias-based ".base_code"
    v := replace(v, 'transgenes.base_code', 'transgenes.transgene_base_code');
    v := regexp_replace(v, '([A-Za-z_][A-Za-z0-9_]*)\.base_code', '\1.transgene_base_code', 'gi');
    EXECUTE 'CREATE OR REPLACE VIEW public.v_fish_overview_v1 AS ' || v;
  END IF;
END$$ LANGUAGE plpgsql;
