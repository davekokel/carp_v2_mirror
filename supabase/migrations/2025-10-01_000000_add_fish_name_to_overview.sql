DO $$
BEGIN
  IF to_regclass('public.fish') IS NOT NULL THEN
    EXECUTE $V$
      CREATE OR REPLACE VIEW public.v_fish_overview AS
      SELECT
        f.id_uuid,
        f.fish_code,
        f.name AS fish_name,
        f.created_at,
        f.created_by
      FROM public.fish f;
    $V$;
  END IF;
END
$$;
