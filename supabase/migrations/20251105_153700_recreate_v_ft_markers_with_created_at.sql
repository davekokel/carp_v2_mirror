BEGIN;

DROP VIEW IF EXISTS public.v_fish_fluorescent_markers;
DROP VIEW IF EXISTS public.v_fluorescent_treatment_markers;

DO $$
DECLARE k text; lbl text;
BEGIN
  IF to_regclass('public.fluors') IS NOT NULL THEN
    SELECT column_name INTO k FROM information_schema.columns
     WHERE table_schema='public' AND table_name='fluors'
       AND data_type IN ('text','character varying')
       AND column_name IN ('code','fluor_code','name')
     ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'fluor_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
     LIMIT 1;
    SELECT CASE WHEN EXISTS (
      SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fluors' AND column_name='name'
    ) THEN 'name' ELSE k END INTO lbl;
    EXECUTE format('CREATE OR REPLACE VIEW public.v_fluors_lu AS SELECT %1$I::text AS code, %2$I::text AS label FROM public.fluors', k, lbl);
  ELSIF to_regclass('public.fluor_names') IS NOT NULL THEN
    SELECT column_name INTO k FROM information_schema.columns
     WHERE table_schema='public' AND table_name='fluor_names'
       AND data_type IN ('text','character varying')
       AND column_name IN ('code','fluor_code','name')
     ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'fluor_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
     LIMIT 1;
    SELECT CASE WHEN EXISTS (
      SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fluor_names' AND column_name='name'
    ) THEN 'name' ELSE k END INTO lbl;
    EXECUTE format('CREATE OR REPLACE VIEW public.v_fluors_lu AS SELECT %1$I::text AS code, %2$I::text AS label FROM public.fluor_names', k, lbl);
  ELSE
    EXECUTE 'CREATE OR REPLACE VIEW public.v_fluors_lu AS SELECT NULL::text AS code, NULL::text AS label WHERE FALSE';
  END IF;

  IF to_regclass('public.tags') IS NOT NULL THEN
    SELECT column_name INTO k FROM information_schema.columns
     WHERE table_schema='public' AND table_name='tags'
       AND data_type IN ('text','character varying')
       AND column_name IN ('code','tag_code','name')
     ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'tag_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
     LIMIT 1;
    SELECT CASE WHEN EXISTS (
      SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tags' AND column_name='name'
    ) THEN 'name' ELSE k END INTO lbl;
    EXECUTE format('CREATE OR REPLACE VIEW public.v_tags_lu AS SELECT %1$I::text AS code, %2$I::text AS label FROM public.tags', k, lbl);
  ELSIF to_regclass('public.tag_names') IS NOT NULL THEN
    SELECT column_name INTO k FROM information_schema.columns
     WHERE table_schema='public' AND table_name='tag_names'
       AND data_type IN ('text','character varying')
       AND column_name IN ('code','tag_code','name')
     ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'tag_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
     LIMIT 1;
    SELECT CASE WHEN EXISTS (
      SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tag_names' AND column_name='name'
    ) THEN 'name' ELSE k END INTO lbl;
    EXECUTE format('CREATE OR REPLACE VIEW public.v_tags_lu AS SELECT %1$I::text AS code, %2$I::text AS label FROM public.tag_names', k, lbl);
  ELSE
    EXECUTE 'CREATE OR REPLACE VIEW public.v_tags_lu AS SELECT NULL::text AS code, NULL::text AS label WHERE FALSE';
  END IF;

  IF to_regclass('public.dyes') IS NOT NULL THEN
    SELECT column_name INTO k FROM information_schema.columns
     WHERE table_schema='public' AND table_name='dyes'
       AND data_type IN ('text','character varying')
       AND column_name IN ('code','dye_code','name')
     ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'dye_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
     LIMIT 1;
    SELECT CASE WHEN EXISTS (
      SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='dyes' AND column_name='name'
    ) THEN 'name' ELSE k END INTO lbl;
    EXECUTE format('CREATE OR REPLACE VIEW public.v_dyes_lu AS SELECT %1$I::text AS code, %2$I::text AS label FROM public.dyes', k, lbl);
  ELSE
    EXECUTE 'CREATE OR REPLACE VIEW public.v_dyes_lu AS SELECT NULL::text AS code, NULL::text AS label WHERE FALSE';
  END IF;
END$$;

CREATE VIEW public.v_fluorescent_treatment_markers AS
SELECT
  p.ft_code,
  'protein'::text AS marker_kind,
  p.fluor_code,
  p.tag_code,
  NULL::text AS dye_code,
  vf.label AS fluor_label,
  vt.label AS tag_label,
  NULL::text AS dye_label,
  COALESCE(vt.label, vf.label) AS marker_label,
  p.created_at
FROM public.ft_proteins p
LEFT JOIN public.v_fluors_lu vf ON vf.code = p.fluor_code
LEFT JOIN public.v_tags_lu   vt ON vt.code = p.tag_code
UNION ALL
SELECT
  d.ft_code,
  'dye'::text AS marker_kind,
  NULL::text AS fluor_code,
  NULL::text AS tag_code,
  d.dye_code,
  NULL::text AS fluor_label,
  NULL::text AS tag_label,
  vd.label AS dye_label,
  vd.label AS marker_label,
  d.created_at
FROM public.ft_dyes d
LEFT JOIN public.v_dyes_lu vd ON vd.code = d.dye_code
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
      m.marker_label,
      COALESCE(j.%5$I, m.created_at) AS linked_at
    FROM public.join_fish_fluorescent_treatments j
    JOIN public.fish f ON f.%1$I = j.%3$I
    JOIN public.v_fluorescent_treatment_markers m ON m.ft_code = j.%4$I
  $v$, fish_pk, fish_code_col, jfish_col, jft_col, COALESCE(jcreated_col,'created_at'));

  EXECUTE sql;
END$$;

COMMIT;
