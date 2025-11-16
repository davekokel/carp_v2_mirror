BEGIN;

DO $$
BEGIN
  PERFORM 1
  FROM pg_class c
  JOIN pg_namespace n ON n.oid = c.relnamespace
  WHERE n.nspname = 'public'
    AND c.relname = 'v_fish_overview_old'
    AND c.relkind = 'v';

  IF NOT FOUND THEN
    BEGIN
      ALTER VIEW public.v_fish_overview RENAME TO v_fish_overview_old;
    EXCEPTION
      WHEN undefined_table THEN
        NULL;
    END;
  END IF;
END
$$;

CREATE OR REPLACE VIEW public.v_fish_overview AS
WITH fish_map AS (
  SELECT
    id,
    fish_code
  FROM public.fish
),
alleles AS (
  SELECT
    jfta.fish_id,
    jfta.transgene_base_code,
    ta.allele_number,
    ta.allele_name,
    ta.allele_nickname
  FROM public.join_fish_transgene_alleles jfta
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jfta.transgene_base_code
   AND ta.allele_number       = jfta.allele_number
),
geno AS (
  SELECT
    a.fish_id,
    string_agg(
      'Tg(' || a.transgene_base_code || ')' || a.allele_name,
      ' + ' ORDER BY a.transgene_base_code, a.allele_number
    ) AS genotype_pretty_raw,
    string_agg(
      'Tg(' || a.transgene_base_code || ')' || a.allele_name,
      ' + ' ORDER BY a.transgene_base_code, a.allele_number
    ) AS transgene_canonical,
    string_agg(
      'Tg(' || a.transgene_base_code || ')' ||
      COALESCE(NULLIF(a.allele_nickname, ''), a.allele_name),
      ' + ' ORDER BY a.transgene_base_code, a.allele_number
    ) AS transgene_nickname,
    string_agg(
      a.transgene_base_code || '(' || a.allele_name || ')',
      ', ' ORDER BY a.transgene_base_code, a.allele_number
    ) AS markers
  FROM alleles a
  GROUP BY a.fish_id
)
SELECT
  old.fish_code_display,
  old.fish_code_raw,
  old.nickname,
  old.birthday,
  old.genetic_background,
  old.line_building_stage,
  COALESCE(NULLIF(g.genotype_pretty_raw, ''), old.genetic_background) AS genotype_pretty,
  g.markers,
  old.fluors,
  old.tags,
  old.fusions,
  old.n_fusions,
  old.dyes,
  old.created_at,
  g.transgene_canonical,
  g.transgene_nickname
FROM public.v_fish_overview_old AS old
LEFT JOIN fish_map fm
  ON fm.fish_code = old.fish_code_raw
LEFT JOIN geno g
  ON g.fish_id = fm.id;

COMMIT;
