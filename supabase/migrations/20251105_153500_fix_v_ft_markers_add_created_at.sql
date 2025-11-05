BEGIN;

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

CREATE OR REPLACE VIEW public.v_fluorescent_treatment_markers AS
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

COMMIT;
