BEGIN;

-- Ensure the helper exists (idempotent)
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

  SELECT COALESCE(NULLIF(TRIM(p.nickname), ''), NULLIF(TRIM(p.name), ''), p.code)
  INTO v_label
  FROM public.plasmids p
  WHERE p.code = p_code;

  RETURN v_label;
END
$fn$;

-- Rename current v_fish_rich to a base name once (no data loss)
DO $$
BEGIN
  IF to_regclass('public.v_fish_rich_base') IS NULL
     AND to_regclass('public.v_fish_rich') IS NOT NULL THEN
    EXECUTE 'ALTER VIEW public.v_fish_rich RENAME TO v_fish_rich_base';
  END IF;
END $$;

-- Rebuild v_fish_rich as base.* + appended columns (only if base exists)
DO $$
DECLARE
  has_base  boolean;
  -- detect if any of the appended columns already exist (append-only safety)
  has_t_codes   boolean;
  has_t_names   boolean;
  has_t_fusions boolean;
  has_g_codes   boolean;
  has_g_fusions boolean;
  has_lin       boolean;
  has_lin_f     boolean;
  has_lin_ff    boolean;
  sql text;
BEGIN
  has_base := (SELECT to_regclass('public.v_fish_rich_base') IS NOT NULL);
  IF NOT has_base THEN
    RETURN;
  END IF;

  has_t_codes   := EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='v_fish_rich_base' AND column_name='fish_treatments_codes');
  has_t_names   := EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='v_fish_rich_base' AND column_name='fish_treatments_names');
  has_t_fusions := EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='v_fish_rich_base' AND column_name='fish_treatments_fusions');
  has_g_codes   := EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='v_fish_rich_base' AND column_name='fish_genotype_codes');
  has_g_fusions := EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='v_fish_rich_base' AND column_name='fish_genotype_fusions');
  has_lin       := EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='v_fish_rich_base' AND column_name='fish_lineage_pretty');
  has_lin_f     := EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='v_fish_rich_base' AND column_name='fish_lineage_fusions_pretty');
  has_lin_ff    := EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='v_fish_rich_base' AND column_name='fish_lineage_full_fusions_pretty');

  sql := 'CREATE OR REPLACE VIEW public.v_fish_rich AS
          WITH base AS (
            SELECT v.* FROM public.v_fish_rich_base v
          ),
          -- Extract plasmid codes from genotype_rollup if it contains Tg(<code>) patterns
          geno_codes AS (
            SELECT
              v.fish_code,
              (regexp_matches(COALESCE(v.genotype_rollup, ''''), ''Tg\(([^)]+)\)'', ''g''))[1]::text AS p_code
            FROM public.v_fish_rich_base v
          ),
          geno_fusions AS (
            SELECT
              g.fish_code,
              public.plasmid_fusion_label(g.p_code) AS fusion_label
            FROM geno_codes g
          ),
          geno_roll AS (
            SELECT
              fish_code,
              STRING_AGG(DISTINCT fusion_label, '';'' ORDER BY fusion_label) AS fish_genotype_fusions_calc
            FROM geno_fusions
            GROUP BY fish_code
          )
          SELECT
            b.*';

  -- Append fish_treatments_* as NULLs (no fish treatments table today)
  IF NOT has_t_codes   THEN sql := sql || ', NULL::text AS fish_treatments_codes';   END IF;
  IF NOT has_t_names   THEN sql := sql || ', NULL::text AS fish_treatments_names';   END IF;
  IF NOT has_t_fusions THEN sql := sql || ', NULL::text AS fish_treatments_fusions'; END IF;

  -- fish_genotype_codes: default to genotype_rollup (canonical codes string today)
  IF NOT has_g_codes THEN
    sql := sql || ', COALESCE(NULLIF(b.genotype_rollup, ''''), NULL) AS fish_genotype_codes';
  END IF;

  -- fish_genotype_fusions: prefer existing fusion_rollup; else computed from regex → helper
  IF NOT has_g_fusions THEN
    sql := sql || ', COALESCE(NULLIF(b.fusion_rollup, ''''), gr.fish_genotype_fusions_calc) AS fish_genotype_fusions';
  END IF;

  -- lineage (no fish treatments yet): show genotype-only
  IF NOT has_lin   THEN sql := sql || ', COALESCE(NULLIF(b.genotype_rollup, ''''), NULL) AS fish_lineage_pretty'; END IF;
  IF NOT has_lin_f THEN sql := sql || ', COALESCE(NULLIF(b.genotype_rollup, ''''), NULL) AS fish_lineage_fusions_pretty'; END IF;
  IF NOT has_lin_ff THEN
    -- full-fusions lineage prefers fusion genotype if present
    sql := sql || ', COALESCE(NULLIF(b.fusion_rollup, ''''), gr.fish_genotype_fusions_calc, b.genotype_rollup) AS fish_lineage_full_fusions_pretty';
  END IF;

  sql := sql || '
          FROM base b
          LEFT JOIN geno_roll gr ON gr.fish_code = b.fish_code';

  EXECUTE sql;
END
$$;

COMMIT;
