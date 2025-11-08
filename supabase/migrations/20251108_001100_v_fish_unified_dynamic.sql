BEGIN;

-- Drop existing views (ignore if missing)
DROP VIEW IF EXISTS public.v_fish_main;
DROP VIEW IF EXISTS public.v_fish_unified;

DO $$
DECLARE
  has_nick    boolean;
  has_bday    boolean;
  has_bg      boolean;
  has_stage   boolean;
  has_created boolean;
  has_rollup  boolean;

  sel_cols    text := 'SELECT f.fish_code';
  sql_text    text;
BEGIN
  -- Detect fish table columns
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='nickname'
  ) INTO has_nick;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='birthday'
  ) INTO has_bday;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='genetic_background'
  ) INTO has_bg;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='line_building_stage'
  ) INTO has_stage;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fish' AND column_name='created_at'
  ) INTO has_created;

  -- Build the SELECT list dynamically (only columns that actually exist)
  IF has_nick    THEN sel_cols := sel_cols || ', f.nickname'; END IF;
  IF has_bday    THEN sel_cols := sel_cols || ', f.birthday'; END IF;
  IF has_bg      THEN sel_cols := sel_cols || ', f.genetic_background'; END IF;
  IF has_stage   THEN sel_cols := sel_cols || ', f.line_building_stage'; END IF;
  IF has_created THEN sel_cols := sel_cols || ', f.created_at'; END IF;

  -- Does v_fluorescent_marker_rollup exist?
  SELECT EXISTS (
    SELECT 1 FROM information_schema.views
    WHERE table_schema='public' AND table_name='v_fluorescent_marker_rollup'
  ) INTO has_rollup;

  -- Assemble CREATE VIEW text with safe DISTINCT+ORDER BY pattern
  sql_text := 'CREATE VIEW public.v_fish_unified AS
WITH markers AS (
  SELECT f.fish_code,
         (ta.transgene_base_code || ''('' || ta.allele_name || '')'')::text AS marker_label
  FROM public.join_fish_transgene_alleles jf
  JOIN public.transgene_alleles ta
    ON ta.transgene_base_code = jf.transgene_base_code
   AND ta.allele_number       = jf.allele_number
  JOIN public.fish f
    ON f.id = jf.fish_id
  WHERE NULLIF(ta.allele_name, '''') IS NOT NULL
),
gp AS (
  SELECT m.fish_code,
         string_agg(DISTINCT m.marker_label, '', '' ORDER BY m.marker_label) AS genotype_pretty
  FROM markers m
  GROUP BY m.fish_code
),
mr AS (';

  IF has_rollup THEN
    sql_text := sql_text ||
      'SELECT r.fish_code, r.markers, r.fluors, r.tags, r.dyes
       FROM public.v_fluorescent_marker_rollup r';
  ELSE
    -- fallback: no rollup view → emit empty strings per fish_code
    sql_text := sql_text ||
      'SELECT f.fish_code,
              ''''::text AS markers,
              ''''::text AS fluors,
              ''''::text AS tags,
              ''''::text AS dyes
       FROM public.fish f';
  END IF;

  sql_text := sql_text || '),
final AS (
  ' || sel_cols || ',
     COALESCE(gp.genotype_pretty, '''') AS genotype_pretty,
     COALESCE(mr.markers,  '''') AS markers,
     COALESCE(mr.fluors,   '''') AS fluors,
     COALESCE(mr.tags,     '''') AS tags,
     COALESCE(mr.dyes,     '''') AS dyes
  FROM public.fish f
  LEFT JOIN gp ON gp.fish_code = f.fish_code
  LEFT JOIN mr ON mr.fish_code = f.fish_code
)
SELECT * FROM final';

  EXECUTE sql_text;

  -- v_fish_main shim over unified (safe, non-recursive)
  EXECUTE 'CREATE VIEW public.v_fish_main AS SELECT * FROM public.v_fish_unified';
END $$;

COMMIT;
