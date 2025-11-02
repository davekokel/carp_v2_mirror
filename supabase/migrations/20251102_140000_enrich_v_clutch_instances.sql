BEGIN;

-- Helper: return a fusion-like label for a plasmid code
-- Priority: linked fusion names (if join_plasmid_fusions exists)
--           → plasmids.nickname → plasmids.name → plasmids.code
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

-- Append-only enrichment:
-- 1) Rename the current view to *_base once (if needed).
DO $$
BEGIN
  IF to_regclass('public.v_clutch_instances_base') IS NULL
     AND to_regclass('public.v_clutch_instances') IS NOT NULL THEN
    EXECUTE 'ALTER VIEW public.v_clutch_instances RENAME TO v_clutch_instances_base';
  END IF;
END $$;

-- 2) Rebuild v_clutch_instances as base.* + 7 appended columns
--    This keeps all prior columns/order intact and appends new fields at the end.
DO $$
BEGIN
  IF to_regclass('public.v_clutch_instances_base') IS NOT NULL THEN
    EXECUTE $v$
      CREATE OR REPLACE VIEW public.v_clutch_instances AS
      WITH base AS (
        SELECT
          v.*,
          v.clutch_genotype_pretty AS clutch_genotype_codes
        FROM public.v_clutch_instances_base v
      ),
      -- Map clutch_code -> clutch_instance_id for treatments
      ci_map AS (
        SELECT ci.id AS clutch_instance_id, ci.clutch_instance_code AS clutch_code
        FROM public.clutch_instances ci
      ),
      -- Normalize treatment codes (prefer *_norm), and carry names
      tx AS (
        SELECT
          m.clutch_code,
          COALESCE(NULLIF(TRIM(ct.treatment_code_norm),''), NULLIF(TRIM(ct.treatment_code), '')) AS t_code,
          NULLIF(TRIM(ct.treatment_name),'') AS t_name
        FROM ci_map m
        JOIN public.join_clutch_treatments ct ON ct.clutch_instance_id = m.clutch_instance_id
      ),
      tx_roll AS (
        SELECT
          clutch_code,
          STRING_AGG(DISTINCT t_code, ';' ORDER BY t_code) AS clutch_treatments_codes,
          STRING_AGG(DISTINCT t_name, ';' ORDER BY t_name) AS clutch_treatments_names
        FROM tx
        GROUP BY clutch_code
      ),
      tx_fusion AS (
        SELECT
          clutch_code,
          STRING_AGG(
            DISTINCT public.plasmid_fusion_label(t_code), ';'
            ORDER BY public.plasmid_fusion_label(t_code)
          ) AS clutch_treatments_fusions
        FROM tx
        WHERE t_code IS NOT NULL
        GROUP BY clutch_code
      ),
      -- Extract Tg(<code>) from genotype string to build genotype fusions
      geno_codes AS (
        SELECT
          b.clutch_code,
          (regexp_matches(b.clutch_genotype_codes, 'Tg\(([^)]+)\)', 'g'))[1]::text AS p_code
        FROM base b
      ),
      geno_fusions AS (
        SELECT
          g.clutch_code,
          public.plasmid_fusion_label(g.p_code) AS fusion_label
        FROM geno_codes g
      ),
      geno_roll AS (
        SELECT
          clutch_code,
          STRING_AGG(DISTINCT fusion_label, ';' ORDER BY fusion_label) AS clutch_genotype_fusions
        FROM geno_fusions
        GROUP BY clutch_code
      )
      SELECT
        b.*,
        -- 7 appended systematic columns
        tr.clutch_treatments_codes,
        tr.clutch_treatments_names,
        tf.clutch_treatments_fusions,
        gr.clutch_genotype_fusions,
        CASE
          WHEN NULLIF(tr.clutch_treatments_codes,'') IS NOT NULL
            THEN tr.clutch_treatments_codes || ' > ' || b.clutch_genotype_codes
          ELSE b.clutch_genotype_codes
        END AS clutch_lineage_pretty,
        CASE
          WHEN NULLIF(tf.clutch_treatments_fusions,'') IS NOT NULL
            THEN tf.clutch_treatments_fusions || ' > ' || b.clutch_genotype_codes
          ELSE b.clutch_genotype_codes
        END AS clutch_lineage_fusions_pretty,
        CASE
          WHEN NULLIF(tf.clutch_treatments_fusions,'') IS NOT NULL
            THEN tf.clutch_treatments_fusions || ' > ' || COALESCE(gr.clutch_genotype_fusions, b.clutch_genotype_codes)
          ELSE COALESCE(gr.clutch_genotype_fusions, b.clutch_genotype_codes)
        END AS clutch_lineage_full_fusions_pretty
      FROM base b
      LEFT JOIN tx_roll  tr ON tr.clutch_code = b.clutch_code
      LEFT JOIN tx_fusion tf ON tf.clutch_code = b.clutch_code
      LEFT JOIN geno_roll gr ON gr.clutch_code = b.clutch_code;
    $v$;
  END IF;
END $$;

COMMIT;
