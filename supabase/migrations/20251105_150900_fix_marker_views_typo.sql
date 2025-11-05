BEGIN;

DROP VIEW IF EXISTS public.v_fish_fluorescent_markers;
DROP VIEW IF EXISTS public.v_fluorescent_treatment_markers;
DROP VIEW IF EXISTS public.v_fluors_lu;
DROP VIEW IF EXISTS public.v_tags_lu;
DROP VIEW IF EXISTS public.v_dyes_lu;
DROP VIEW IF EXISTS public.v_fish_import_ft_missing;

DO $$
DECLARE k text; lbl text;
BEGIN
  IF to_regclass('public.fluors') IS NOT NULL THEN
    SELECT column_name INTO k
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fluors'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','fluor_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'fluor_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
    LIMIT 1;
    SELECT CASE WHEN EXISTS (
             SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='fluors' AND column_name='name'
           ) THEN 'name' ELSE k END INTO lbl;
    EXECUTE format('CREATE VIEW public.v_fluors_lu AS SELECT %1$I::text AS code, %2$I::text AS label FROM public.fluors', k, lbl);
  ELSIF to_regclass('public.fluor_names') IS NOT NULL THEN
    SELECT column_name INTO k
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fluor_names'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','fluor_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'fluor_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
    LIMIT 1;
    SELECT CASE WHEN EXISTS (
             SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='fluor_names' AND column_name='name'
           ) THEN 'name' ELSE k END INTO lbl;
    EXECUTE format('CREATE VIEW public.v_fluors_lu AS SELECT %1$I::text AS code, %2$I::text AS label FROM public.fluor_names', k, lbl);
  ELSE
    EXECUTE 'CREATE VIEW public.v_fluors_lu AS SELECT NULL::text AS code, NULL::text AS label WHERE FALSE';
  END IF;

  IF to_regclass('public.tags') IS NOT NULL THEN
    SELECT column_name INTO k
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tags'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','tag_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'tag_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
    LIMIT 1;
    SELECT CASE WHEN EXISTS (
             SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='tags' AND column_name='name'
           ) THEN 'name' ELSE k END INTO lbl;
    EXECUTE format('CREATE VIEW public.v_tags_lu AS SELECT %1$I::text AS code, %2$I::text AS label FROM public.tags', k, lbl);
  ELSIF to_regclass('public.tag_names') IS NOT NULL THEN
    SELECT column_name INTO k
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tag_names'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','tag_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'tag_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
    LIMIT 1;
    SELECT CASE WHEN EXISTS (
             SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='tag_names' AND column_name='name'
           ) THEN 'name' ELSE k END INTO lbl;
    EXECUTE format('CREATE VIEW public.v_tags_lu AS SELECT %1$I::text AS code, %2$I::text AS label FROM public.tag_names', k, lbl);
  ELSE
    EXECUTE 'CREATE VIEW public.v_tags_lu AS SELECT NULL::text AS code, NULL::text AS label WHERE FALSE';
  END IF;

  IF to_regclass('public.dyes') IS NOT NULL THEN
    SELECT column_name INTO k
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='dyes'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','dye_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'dye_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
    LIMIT 1;
    SELECT CASE WHEN EXISTS (
             SELECT 1 FROM information_schema.columns
             WHERE table_schema='public' AND table_name='dyes' AND column_name='name'
           ) THEN 'name' ELSE k END INTO lbl;
    EXECUTE format('CREATE VIEW public.v_dyes_lu AS SELECT %1$I::text AS code, %2$I::text AS label FROM public.dyes', k, lbl);
  ELSE
    EXECUTE 'CREATE VIEW public.v_dyes_lu AS SELECT NULL::text AS code, NULL::text AS label WHERE FALSE';
  END IF;
END$$;

CREATE VIEW public.v_fluorescent_treatment_markers AS
SELECT
  pm.ft_code,
  'protein'::text AS marker_kind,
  pm.fluor_code,
  pm.tag_code,
  vf.label AS fluor_label,
  vt.label AS tag_label,
  NULL::text AS dye_code,
  NULL::text AS dye_label,
  pm.created_at
FROM public.ft_protein_markers pm
LEFT JOIN public.v_fluors_lu vf ON vf.code = pm.fluor_code
LEFT JOIN public.v_tags_lu   vt ON vt.code = pm.tag_code
UNION ALL
SELECT
  dm.ft_code,
  'dye'::text AS marker_kind,
  NULL::text AS fluor_code,
  NULL::text AS tag_code,
  NULL::text AS fluor_label,
  NULL::text AS tag_label,
  dm.dye_code,
  vd.label AS dye_label,
  dm.created_at
FROM public.ft_dye_markers dm
LEFT JOIN public.v_dyes_lu vd ON vd.code = dm.dye_code
;

DO $$
DECLARE fish_pk text; fish_code_col text; jfish_col text; jft_col text; jcreated_col text; sql text;
BEGIN
  SELECT column_name INTO fish_pk
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

  IF fish_pk IS NULL OR fish_code_col IS NULL OR jfish_col IS NULL OR jft_col IS NULL THEN
    RAISE EXCEPTION 'Missing required columns (fish_pk=%, fish_code_col=%, jfish_col=%, jft_col=%)', fish_pk, fish_code_col, jfish_col, jft_col;
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
    JOIN public.fish f ON f.%1$I = j.%3$I
    JOIN public.v_fluorescent_treatment_markers m ON m.ft_code = j.%4$I
  $v$, fish_pk, fish_code_col, jfish_col, jft_col, COALESCE(jcreated_col, 'created_at'));

  EXECUTE sql;
END$$;

CREATE VIEW public.v_fish_import_ft_missing AS
SELECT
  j.fish_id,
  j.ft_code,
  CASE WHEN ft.ft_code IS NOT NULL THEN 'present_in_ft'
       WHEN mix.ft_code IS NOT NULL THEN 'present_in_mix'
       ELSE 'missing'
  END AS status
FROM public.join_fish_fluorescent_treatments j
LEFT JOIN public.fluorescent_treatments ft ON ft.ft_code = j.ft_code
LEFT JOIN public.ft_injection_mixes   mix  ON mix.ft_code = j.ft_code
WHERE ft.ft_code IS NULL AND mix.ft_code IS NULL;

COMMIT;
