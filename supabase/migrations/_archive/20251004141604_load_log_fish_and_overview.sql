BEGIN;

-- 1) ensure load_log_fish exists with required columns/constraints
CREATE TABLE IF NOT EXISTS public.load_log_fish (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fish_id uuid NOT NULL REFERENCES public.fish (id) ON DELETE CASCADE,
    seed_batch_id text NOT NULL,
    row_key text NOT NULL,
    logged_at timestamptz NOT NULL DEFAULT now()
);
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='load_log_fish' AND column_name='row_key'
  ) THEN
    ALTER TABLE public.load_log_fish ADD COLUMN row_key text NOT NULL DEFAULT '';
    ALTER TABLE public.load_log_fish ALTER COLUMN row_key DROP DEFAULT;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM information_schema.table_constraints
    WHERE table_schema='public' AND table_name='load_log_fish'
      AND constraint_type='UNIQUE' AND constraint_name='uq_load_log_fish_batch_row'
  ) THEN
    ALTER TABLE public.load_log_fish
      ADD CONSTRAINT uq_load_log_fish_batch_row UNIQUE (seed_batch_id, row_key);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='load_log_fish' AND indexname='idx_load_log_fish_fish_id'
  ) THEN
    CREATE INDEX idx_load_log_fish_fish_id ON public.load_log_fish(fish_id);
  END IF;
END$$;

-- 2) recreate overview view; prefer seed_batch_id as batch_label when present
DROP VIEW IF EXISTS public.vw_fish_overview_with_label;

CREATE VIEW public.vw_fish_overview_with_label AS
WITH base AS (
    SELECT
        v.id,
        v.fish_code,
        v.name,
        v.transgene_base_code_filled,
        v.allele_code_filled,
        v.allele_name_filled,
        v.created_at,
        v.created_by,
        f.nickname,
        f.line_building_stage,
        f.date_birth,
        coalesce(f.created_by, v.created_by) AS created_by_enriched
    FROM public.v_fish_overview AS v
    LEFT JOIN public.fish AS f ON v.fish_code = f.fish_code
),

batch AS (
    SELECT
        fish_id,
        max(seed_batch_id) AS seed_batch_id
    FROM public.load_log_fish
    GROUP BY fish_id
),

prefer AS (
    SELECT
        b.*,
        coalesce(
            bt.seed_batch_id,
            substring(b.fish_code FROM '^FSH-([0-9]{2}[0-9A-Z]{4,})'),
            b.fish_code
        ) AS batch_label
    FROM base AS b
    LEFT JOIN batch AS bt ON b.id = bt.fish_id
)

SELECT
    p.id,
    p.fish_code,
    p.name,
    p.transgene_base_code_filled,
    p.allele_code_filled,
    p.allele_name_filled,
    p.created_at,
    p.created_by,
    p.nickname,
    p.line_building_stage,
    p.date_birth,
    p.batch_label,
    p.created_by_enriched,
    NULL::timestamptz AS last_plasmid_injection_at,
    NULL::text AS plasmid_injections_text,
    NULL::timestamptz AS last_rna_injection_at,
    NULL::text AS rna_injections_text,
    CASE WHEN p.date_birth IS NOT NULL THEN (current_date - p.date_birth) END AS age_days,
    CASE WHEN p.date_birth IS NOT NULL THEN floor(((current_date - p.date_birth)::numeric) / 7)::int END AS age_weeks
FROM prefer AS p;

COMMIT;
