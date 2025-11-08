BEGIN;

DROP VIEW IF EXISTS public.v_fluorescent_marker_rollup;

DO $$
DECLARE
  fluor_label_col text;
  tag_label_col   text;
  dye_label_col   text;
  has_dye_col     boolean;
  has_dyes_table  boolean;
  sql_text        text;
BEGIN
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fusions' AND column_name='dye_id'
  ) INTO has_dye_col;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='dyes'
  ) INTO has_dyes_table;

  SELECT CASE
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fluors' AND column_name='name') THEN 'name'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fluors' AND column_name='label') THEN 'label'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='fluors' AND column_name='code') THEN 'code'
           ELSE NULL
         END
  INTO fluor_label_col;

  SELECT CASE
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tags' AND column_name='name') THEN 'name'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tags' AND column_name='label') THEN 'label'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='tags' AND column_name='code') THEN 'code'
           ELSE NULL
         END
  INTO tag_label_col;

  SELECT CASE
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='dyes' AND column_name='name') THEN 'name'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='dyes' AND column_name='label') THEN 'label'
           WHEN EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='dyes' AND column_name='code') THEN 'code'
           ELSE NULL
         END
  INTO dye_label_col;

  sql_text := format($v$
    CREATE VIEW public.v_fluorescent_marker_rollup AS
    WITH base AS (
      SELECT
        f.fish_code,
        ta.transgene_base_code,
        ta.allele_number,
        p.id AS plasmid_id
      FROM public.fish f
      JOIN public.join_fish_transgene_alleles jf
        ON jf.fish_id = f.id
      JOIN public.transgene_alleles ta
        ON ta.transgene_base_code = jf.transgene_base_code
       AND ta.allele_number       = jf.allele_number
      JOIN public.plasmids p
        ON p.code = ta.transgene_base_code
    ),
    fus AS (
      SELECT DISTINCT
        b.fish_code,
        b.transgene_base_code,
        b.allele_number,
        fu.fluor_id,
        fu.tag_id
        %s
      FROM base b
      LEFT JOIN public.join_plasmid_fusions jpf ON jpf.plasmid_id = b.plasmid_id
      LEFT JOIN public.fusions fu               ON fu.id = jpf.fusion_id
    )
    SELECT
      b.fish_code,
      string_agg(DISTINCT (b.transgene_base_code || b.allele_number::text), ',' ORDER BY (b.transgene_base_code || b.allele_number::text)) AS markers,
      %s AS fluors,
      %s AS tags,
      %s AS dyes
    FROM base b
    LEFT JOIN fus x ON x.fish_code=b.fish_code AND x.transgene_base_code=b.transgene_base_code AND x.allele_number=b.allele_number
    %s
    GROUP BY b.fish_code;
  $v$,
    CASE WHEN has_dye_col THEN ', fu.dye_id' ELSE '' END,
    CASE WHEN fluor_label_col IS NOT NULL
         THEN format('COALESCE(string_agg(DISTINCT fl.%1$s, '','' ORDER BY fl.%1$s), '''')', fluor_label_col)
         ELSE '''''' END,
    CASE WHEN tag_label_col IS NOT NULL
         THEN format('COALESCE(string_agg(DISTINCT tg.%1$s, '','' ORDER BY tg.%1$s), '''')', tag_label_col)
         ELSE '''''' END,
    CASE
      WHEN has_dye_col AND has_dyes_table AND dye_label_col IS NOT NULL
      THEN format('COALESCE(string_agg(DISTINCT dy.%1$s, '','' ORDER BY dy.%1$s), '''')', dye_label_col)
      ELSE '''''' END,
    CASE
      WHEN fluor_label_col IS NOT NULL AND tag_label_col IS NOT NULL AND has_dye_col AND has_dyes_table AND dye_label_col IS NOT NULL
      THEN format('LEFT JOIN public.fluors fl ON fl.id = x.fluor_id
                   LEFT JOIN public.tags   tg ON tg.id = x.tag_id
                   LEFT JOIN public.dyes   dy ON dy.id = x.dye_id')
      WHEN fluor_label_col IS NOT NULL AND tag_label_col IS NOT NULL
      THEN format('LEFT JOIN public.fluors fl ON fl.id = x.fluor_id
                   LEFT JOIN public.tags   tg ON tg.id = x.tag_id')
      WHEN fluor_label_col IS NOT NULL
      THEN format('LEFT JOIN public.fluors fl ON fl.id = x.fluor_id')
      WHEN tag_label_col IS NOT NULL
      THEN format('LEFT JOIN public.tags tg ON tg.id = x.tag_id')
      ELSE '' END
  );

  EXECUTE sql_text;
END $$;

COMMIT;
