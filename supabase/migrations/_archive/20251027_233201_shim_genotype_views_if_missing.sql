DO $$
BEGIN
  IF to_regclass('public.v_transgene_alleles') IS NULL THEN
    CREATE VIEW public.v_transgene_alleles AS
    SELECT f.fish_uuid::uuid AS fish_uuid,
           0::int           AS allele_number,
           NULL::text       AS allele_code
    FROM public.fish f;
  END IF;

  IF to_regclass('public.v_fish_genotypes') IS NULL THEN
    CREATE VIEW public.v_fish_genotypes AS
    SELECT f.fish_uuid::uuid AS fish_uuid,
           NULL::text        AS transgene_pretty,
           NULL::text        AS genotype_rollup
    FROM public.fish f;
  END IF;
END$$;
