BEGIN;

CREATE OR REPLACE VIEW public.v_fish_overview AS
WITH base AS (
  SELECT
    f.id,
    f.fish_code,
    f.nickname,
    f.genetic_background,
    f.birthday,
    f.created_at
  FROM public.fish_instance f
),
alleles AS (
  SELECT
    j.fish_id,
    string_agg(DISTINCT j.transgene_base_code, ', ' ORDER BY j.transgene_base_code)
      AS genotype_base_codes,
    string_agg(
      'Tg(' || j.transgene_base_code || ')' ||
      COALESCE(
        NULLIF(a.allele_name, ''),
        'gu' || j.allele_number::text
      ),
      '; ' ORDER BY j.transgene_base_code, j.allele_number
    ) AS genotype_alleles_pretty
  FROM public.join_fish_transgene_alleles j
  LEFT JOIN public.transgene_alleles a
    ON a.transgene_base_code = j.transgene_base_code
   AND a.allele_number       = j.allele_number
  GROUP BY j.fish_id
),
joined AS (
  SELECT
    b.id,
    b.fish_code,
    b.nickname,
    b.genetic_background,
    b.birthday,
    b.created_at,
    a.genotype_base_codes,
    a.genotype_alleles_pretty,
    COALESCE(
      a.genotype_alleles_pretty,
      NULLIF(b.genetic_background, ''),
      'WT'
    ) AS genotype_pretty,
    CASE
      WHEN a.genotype_base_codes IS NOT NULL THEN 'canonical'
      WHEN b.genetic_background IS NOT NULL AND b.genetic_background <> '' THEN 'background'
      ELSE 'needs_manual'
    END AS genotype_source
  FROM base b
  LEFT JOIN alleles a ON a.fish_id = b.id
)
SELECT *
FROM joined
ORDER BY fish_code;

COMMIT;
