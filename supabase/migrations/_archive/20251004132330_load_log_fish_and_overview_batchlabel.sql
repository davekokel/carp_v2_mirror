BEGIN;

-- 1) Lightweight load log keyed by batch (CSV filename) + row_key
CREATE TABLE IF NOT EXISTS public.load_log_fish (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_id       uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
  seed_batch_id text NOT NULL,
  row_key       text NOT NULL,                     -- stable hash of normalized row
  logged_at     timestamptz NOT NULL DEFAULT now(),
  UNIQUE (seed_batch_id, row_key)
);

-- 2) Recreate the overview view so batch_label prefers the seed_batch_id when present
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
    COALESCE(f.created_by, v.created_by) AS created_by_enriched
  FROM public.v_fish_overview v
  LEFT JOIN public.fish f ON f.fish_code = v.fish_code
),
batch AS (
  SELECT fish_id, max(seed_batch_id) AS seed_batch_id
  FROM public.load_log_fish
  GROUP BY fish_id
),
prefer AS (
  SELECT
    b.*,
    COALESCE(bt.seed_batch_id,
             SUBSTRING(b.fish_code FROM '^FSH-([0-9]{2}[0-9A-Z]{4,})'),
             b.fish_code) AS batch_label
  FROM base b
  LEFT JOIN batch bt ON bt.fish_id = b.id
),
links AS (
  SELECT
    fta.fish_id,
    STRING_AGG(DISTINCT COALESCE(fta.zygosity,'unknown'), ', ' ORDER BY COALESCE(fta.zygosity,'unknown')) AS zygosity_text,
    STRING_AGG(DISTINCT COALESCE(reg.allele_nickname,''), ', ' ORDER BY COALESCE(reg.allele_nickname,'')) AS link_nicknames_text
  FROM public.fish_transgene_alleles fta
  LEFT JOIN public.transgene_allele_registry reg
    ON reg.transgene_base_code = fta.transgene_base_code
   AND reg.allele_number = fta.allele_number
  GROUP BY fta.fish_id
)
SELECT
  p.id,
  p.fish_code,
  p.name,
  p.transgene_base_code_filled,
  p.allele_code_filled,
  p.allele_name_filled,
  (p.transgene_base_code_filled || ' : ' || p.allele_name_filled) AS genotype_display,
  p.created_at,
  p.created_by,
  p.nickname,
  p.line_building_stage,
  p.date_birth,
  p.batch_label,
  p.created_by_enriched,
  CASE WHEN p.date_birth IS NOT NULL THEN (CURRENT_DATE - p.date_birth) END AS age_days,
  CASE WHEN p.date_birth IS NOT NULL THEN FLOOR(((CURRENT_DATE - p.date_birth)::numeric)/7)::int END AS age_weeks,
  NULL::timestamptz AS last_plasmid_injection_at,
  NULL::text        AS plasmid_injections_text,
  NULL::timestamptz AS last_rna_injection_at,
  NULL::text        AS rna_injections_text,
  l.zygosity_text,
  l.link_nicknames_text
FROM prefer p
LEFT JOIN links l ON l.fish_id = p.id;

COMMIT;
