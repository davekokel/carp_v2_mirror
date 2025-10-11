BEGIN;

-- 1) Normalize transgene_allele_registry to modern columns (legacy-safe)
DO $$
DECLARE
  has_mod_base    boolean;
  has_mod_nick    boolean;
  has_legacy_base boolean;
  has_legacy_nick boolean;
BEGIN
  IF to_regclass('public.transgene_allele_registry') IS NULL THEN
    CREATE TABLE public.transgene_allele_registry(
      id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      transgene_base_code text NOT NULL,
      allele_number integer NOT NULL,
      allele_nickname text NOT NULL,
      created_at timestamptz NOT NULL DEFAULT now(),
      created_by text NULL
    );
  ELSE
    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='transgene_allele_registry'
        AND column_name='transgene_base_code'
    ) INTO has_mod_base;

    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='transgene_allele_registry'
        AND column_name='allele_nickname'
    ) INTO has_mod_nick;

    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='transgene_allele_registry'
        AND column_name='base_code'
    ) INTO has_legacy_base;

    SELECT EXISTS (
      SELECT 1 FROM information_schema.columns
      WHERE table_schema='public' AND table_name='transgene_allele_registry'
        AND column_name='legacy_label'
    ) INTO has_legacy_nick;

    -- add modern columns if missing (nullable), then backfill from legacy
    IF NOT has_mod_base THEN
      ALTER TABLE public.transgene_allele_registry ADD COLUMN transgene_base_code text;
    END IF;
    IF NOT has_mod_nick THEN
      ALTER TABLE public.transgene_allele_registry ADD COLUMN allele_nickname text;
    END IF;

    IF has_legacy_base AND has_legacy_nick THEN
      -- backfill modern cols from legacy where empty
      EXECUTE $Q$
        UPDATE public.transgene_allele_registry
           SET transgene_base_code = COALESCE(transgene_base_code, base_code),
               allele_nickname     = COALESCE(allele_nickname,     legacy_label)
      $Q$;
    END IF;
  END IF;

  -- unique indexes on modern columns (idempotent)
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='uq_tar_base_number' AND relkind='i') THEN
    CREATE UNIQUE INDEX uq_tar_base_number
      ON public.transgene_allele_registry (transgene_base_code, allele_number);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='uq_tar_base_nickname' AND relkind='i') THEN
    CREATE UNIQUE INDEX uq_tar_base_nickname
      ON public.transgene_allele_registry (transgene_base_code, allele_nickname);
  END IF;
END
$$;

-- 2) Ensure counters table exists
DO $$
BEGIN
  IF to_regclass('public.transgene_allele_counters') IS NULL THEN
    CREATE TABLE public.transgene_allele_counters(
      transgene_base_code text PRIMARY KEY,
      next_number integer NOT NULL DEFAULT 1
    );
  END IF;
END
$$;

-- 3) Rebuild label view minimally on top of base
DROP VIEW IF EXISTS public.vw_fish_overview_with_label;

CREATE VIEW public.vw_fish_overview_with_label AS
SELECT
  v.id,
  v.fish_code,
  v.name,
  v.transgene_base_code_filled,
  v.allele_code_filled,
  v.allele_name_filled,
  v.created_at,
  v.created_by,
  -- pretty string using numeric or nickname if you prefer later
  CASE
    WHEN v.transgene_base_code_filled IS NOT NULL AND v.allele_code_filled IS NOT NULL
      THEN v.transgene_base_code_filled || ' : ' || v.allele_code_filled
    ELSE NULL
  END AS transgene_pretty,
  f.nickname,
  f.line_building_stage,
  f.date_birth,
  NULL::text        AS batch_label,
  NULL::text        AS created_by_enriched,
  NULL::timestamptz AS last_plasmid_injection_at,
  NULL::text        AS plasmid_injections_text,
  NULL::timestamptz AS last_rna_injection_at,
  NULL::text        AS rna_injections_text
FROM public.v_fish_overview v
LEFT JOIN public.fish f
  ON f.id = v.id;

COMMIT;
