BEGIN;

DROP VIEW IF EXISTS public.v_fish_fluorescent_markers;

DO $$
DECLARE
  fish_key text;
  fish_code_col text;
  jfish_col text;
  jft_col text;
  jcreated_col text;
  sql text;
BEGIN
  SELECT column_name INTO fish_key
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='fish'
    AND column_name IN ('fish_uuid','id','uuid')
  ORDER BY CASE column_name WHEN 'fish_uuid' THEN 1 WHEN 'id' THEN 2 WHEN 'uuid' THEN 3 ELSE 9 END
  LIMIT 1;

  SELECT column_name INTO fish_code_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='fish'
    AND column_name IN ('fish_code','code','name')
  ORDER BY CASE column_name WHEN 'fish_code' THEN 1 WHEN 'code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
  LIMIT 1;

  SELECT column_name INTO jfish_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='join_fish_fluorescent_treatments'
    AND column_name IN ('fish_uuid','fish_id','fish_code')
  ORDER BY CASE column_name WHEN 'fish_uuid' THEN 1 WHEN 'fish_id' THEN 2 WHEN 'fish_code' THEN 3 ELSE 9 END
  LIMIT 1;

  SELECT column_name INTO jft_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='join_fish_fluorescent_treatments'
    AND column_name IN ('ft_code','fluorescent_treatment_code','treatment_code')
  ORDER BY CASE column_name WHEN 'ft_code' THEN 1 WHEN 'fluorescent_treatment_code' THEN 2 WHEN 'treatment_code' THEN 3 ELSE 9 END
  LIMIT 1;

  SELECT column_name INTO jcreated_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='join_fish_fluorescent_treatments'
    AND column_name IN ('created_at','linked_at','updated_at')
  ORDER BY CASE column_name WHEN 'created_at' THEN 1 WHEN 'linked_at' THEN 2 WHEN 'updated_at' THEN 3 ELSE 9 END
  LIMIT 1;

  IF fish_key IS NULL OR fish_code_col IS NULL OR jfish_col IS NULL OR jft_col IS NULL THEN
    RAISE EXCEPTION 'Missing required columns (fish_key=%, fish_code_col=%, jfish_col=%, jft_col=%)',
      fish_key, fish_code_col, jfish_col, jft_col;
  END IF;

  sql := format($v$
    CREATE VIEW public.v_fish_fluorescent_markers AS
    SELECT
      f.%1$I        AS fish_pk,
      f.%2$I::text  AS fish_code,
      j.%3$I::text  AS fish_ref_in_join,
      j.%4$I::text  AS ft_code,
      m.marker_kind,
      m.fluor_code,
      m.fluor_label,
      m.tag_code,
      m.tag_label,
      m.dye_code,
      m.dye_label,
      COALESCE(j.%5$I, m.created_at) AS linked_at
    FROM public.join_fish_fluorescent_treatments j
    JOIN public.fish f
      ON f.%1$I = j.%3$I
    JOIN public.v_fluorescent_treatment_markers m
      ON m.ft_code = j.%4$I
  $v$, fish_key, fish_code_col, jfish_col, jft_col, COALESCE(jcreated_col, 'created_at'));

  EXECUTE sql;
END$$;

COMMIT;
