BEGIN;

-- Helper: code → fusion-like label (fusions > nickname > name > code)
CREATE OR REPLACE FUNCTION public.plasmid_fusion_label(p_code text)
RETURNS text
LANGUAGE plpgsql
STABLE
AS $fn$
DECLARE
  v_label text;
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_plasmid_fusions' AND column_name='plasmid_id'
  ) THEN
    SELECT STRING_AGG(DISTINCT f.fusion_name, ';' ORDER BY f.fusion_name)
      INTO v_label
    FROM public.plasmids p
    JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = p.id
    JOIN public.fusions f               ON f.fusion_code   = jpf.fusion_code
    WHERE p.code = p_code;
    IF COALESCE(v_label,'') <> '' THEN
      RETURN v_label;
    END IF;
  END IF;

  SELECT COALESCE(NULLIF(TRIM(p.nickname), ''),
                  NULLIF(TRIM(p.name), ''),
                  p.code)
    INTO v_label
  FROM public.plasmids p
  WHERE p.code = p_code;

  RETURN v_label;
END
$fn$;

-- Rename once to a base name so we can rebuild cleanly without self-reference
DO $$
BEGIN
  IF to_regclass('public.v_plasmids_rich_base') IS NULL
     AND to_regclass('public.v_plasmids_rich')     IS NOT NULL THEN
    EXECUTE 'ALTER VIEW public.v_plasmids_rich RENAME TO v_plasmids_rich_base';
  END IF;
END $$;

-- Rebuild v_plasmids_rich as base.* + appended columns (only if base exists)
DO $$
DECLARE
  has_base     boolean;
  has_code     boolean;
  has_id       boolean;
  has_fnames   boolean;   -- base has fusion_names?
  has_pname    boolean;   -- base has plasmid_name?
  has_nick     boolean;   -- base has nickname?
  sql text;
  join_on text;
  fusion_expr text;
BEGIN
  has_base := (SELECT to_regclass('public.v_plasmids_rich_base') IS NOT NULL);
  IF NOT has_base THEN
    -- nothing to do
    RETURN;
  END IF;

  has_code := EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='v_plasmids_rich_base' AND column_name='plasmid_code'
  );
  has_id := EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='v_plasmids_rich_base' AND column_name='plasmid_id'
  );
  has_fnames := EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='v_plasmids_rich_base' AND column_name='fusion_names'
  );
  has_pname := EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='v_plasmids_rich_base' AND column_name='plasmid_name'
  );
  has_nick := EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='v_plasmids_rich_base' AND column_name='nickname'
  );

  -- Build JOIN clause depending on what keys base exposes
  IF has_nick AND has_pname THEN
    join_on := '( (v.nickname IS NOT NULL AND p.nickname = v.nickname) OR (v.nickname IS NULL AND v.plasmid_name IS NOT NULL AND p.name = v.plasmid_name) )';
  ELSIF has_nick THEN
    join_on := '( p.nickname = v.nickname )';
  ELSIF has_pname THEN
    join_on := '( p.name = v.plasmid_name )';
  ELSE
    -- no join keys available; produce NULLs for appended columns
    join_on := 'FALSE';
  END IF;

  -- Choose fusion expression: use base.fusion_names if present, else helper
  IF has_fnames THEN
    fusion_expr := 'COALESCE(NULLIF(v.fusion_names, ''''), public.plasmid_fusion_label(p.code)) AS plasmid_fusion_pretty';
  ELSE
    fusion_expr := 'public.plasmid_fusion_label(p.code) AS plasmid_fusion_pretty';
  END IF;

  sql := 'CREATE OR REPLACE VIEW public.v_plasmids_rich AS
          SELECT
            v.*';

  IF NOT has_code THEN
    sql := sql || ', p.code AS plasmid_code';
  END IF;

  IF NOT has_id THEN
    sql := sql || ', p.id   AS plasmid_id';
  END IF;

  sql := sql || ', ' || fusion_expr || '
          FROM public.v_plasmids_rich_base v
          LEFT JOIN public.plasmids p
            ON ' || join_on;

  EXECUTE sql;
END
$$;

COMMIT;
