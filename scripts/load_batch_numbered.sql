-- scripts/load_batch_numbered.sql
-- Run with:
--   psql "$LOCAL_DB_URL" -v ON_ERROR_STOP=1 -v batchdir="$BATCH_DIR" -f scripts/load_batch_numbered.sql

\echo Using batchdir = :batchdir

-- Build numbered file paths (UNQUOTED here)
\set file_fish    :batchdir '/01_fish.csv'
\set file_tg      :batchdir '/02_transgenes.csv'
\set file_alleles :batchdir '/03_transgene_alleles.csv'
\set file_links   :batchdir '/10_fish_transgene_alleles.csv'

BEGIN;

-- Idempotent shapes / indexes
ALTER TABLE public.fish
  ADD COLUMN IF NOT EXISTS fish_code           text,
  ADD COLUMN IF NOT EXISTS name                text,
  ADD COLUMN IF NOT EXISTS date_of_birth       date,
  ADD COLUMN IF NOT EXISTS line_building_stage text,
  ADD COLUMN IF NOT EXISTS strain              text;
CREATE UNIQUE INDEX IF NOT EXISTS fish_fish_code_key ON public.fish(fish_code);

ALTER TABLE public.transgenes
  ADD COLUMN IF NOT EXISTS transgene_base_code text,
  ADD COLUMN IF NOT EXISTS name                text,
  ADD COLUMN IF NOT EXISTS description         text;
CREATE UNIQUE INDEX IF NOT EXISTS transgenes_transgene_base_code_key
  ON public.transgenes(transgene_base_code);

ALTER TABLE public.transgene_alleles
  ADD COLUMN IF NOT EXISTS transgene_base_code text,
  ADD COLUMN IF NOT EXISTS allele_number       text,
  ADD COLUMN IF NOT EXISTS description         text;
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid = 'public.transgene_alleles'::regclass AND contype='p'
  ) THEN
    ALTER TABLE public.transgene_alleles
      ADD CONSTRAINT transgene_alleles_pk PRIMARY KEY (transgene_base_code, allele_number);
  END IF;
END$$;
CREATE INDEX IF NOT EXISTS transgene_alleles_base_allele_idx
  ON public.transgene_alleles (transgene_base_code, allele_number);

CREATE UNIQUE INDEX IF NOT EXISTS fish_transgene_alleles_uniq
  ON public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number);

-- Staging tables
DROP TABLE IF EXISTS core_fish_csv;
DROP TABLE IF EXISTS core_transgenes_csv;
DROP TABLE IF EXISTS core_transgene_alleles_csv;
DROP TABLE IF EXISTS core_fish_transgene_alleles_csv;

CREATE TEMP TABLE core_fish_csv (
  fish_code           text,
  name                text,
  date_of_birth       text,
  line_building_stage text,
  strain              text
);
CREATE TEMP TABLE core_transgenes_csv (
  transgene_base_code text,
  name                text,
  description         text
);
CREATE TEMP TABLE core_transgene_alleles_csv (
  transgene_base_code text,
  allele_number       text,
  description         text
);
CREATE TEMP TABLE core_fish_transgene_alleles_csv (
  fish_code            text,
  transgene_base_code  text,
  allele_number        text
);

-- Load (only the FROM side needs the QUOTED :'var')
\echo copying :file_fish
\copy core_fish_csv                   from :'file_fish'    with (format csv, header true)
\echo copying :file_tg
\copy core_transgenes_csv             from :'file_tg'      with (format csv, header true)
\echo copying :file_alleles
\copy core_transgene_alleles_csv      from :'file_alleles' with (format csv, header true)
\echo copying :file_links
\copy core_fish_transgene_alleles_csv from :'file_links'   with (format csv, header true)

-- Upsert fish
WITH pf AS (
  SELECT
    lower(trim(fish_code))               AS fish_code,
    NULLIF(trim(name), '')               AS name,
    CASE
      WHEN trim(date_of_birth) ~ '^[0-9]{4}-[0-9]{2}-[0-9]{2}$' THEN (trim(date_of_birth))::date
      WHEN trim(date_of_birth) ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{2}$' THEN to_date(trim(date_of_birth),'MM/DD/YY')
      WHEN trim(date_of_birth) ~ '^[0-9]{1,2}/[0-9]{1,2}/[0-9]{4}$' THEN to_date(trim(date_of_birth),'MM/DD/YYYY')
      ELSE NULL::date
    END                                   AS date_of_birth,
    NULLIF(trim(line_building_stage), '') AS line_building_stage,
    NULLIF(trim(strain), '')              AS strain
  FROM core_fish_csv
  WHERE COALESCE(trim(fish_code),'') <> ''
)
INSERT INTO public.fish (fish_code, name, date_of_birth, line_building_stage, strain)
SELECT fish_code, name, date_of_birth, line_building_stage, strain
FROM pf
ON CONFLICT (fish_code) DO UPDATE
SET name                = EXCLUDED.name,
    date_of_birth       = EXCLUDED.date_of_birth,
    line_building_stage = EXCLUDED.line_building_stage,
    strain              = EXCLUDED.strain;

-- Upsert transgenes
INSERT INTO public.transgenes (transgene_base_code, name, description)
SELECT lower(trim(transgene_base_code)),
       NULLIF(trim(name), ''),
       NULLIF(trim(description), '')
FROM core_transgenes_csv
WHERE COALESCE(trim(transgene_base_code),'') <> ''
ON CONFLICT (transgene_base_code) DO UPDATE
SET name = EXCLUDED.name, description = EXCLUDED.description;

-- Upsert alleles
INSERT INTO public.transgene_alleles (transgene_base_code, allele_number, description)
SELECT lower(trim(transgene_base_code)),
       lower(trim(allele_number)),
       NULLIF(trim(description), '')
FROM core_transgene_alleles_csv
WHERE COALESCE(trim(transgene_base_code),'') <> ''
  AND COALESCE(trim(allele_number),'') <> ''
ON CONFLICT (transgene_base_code, allele_number) DO UPDATE
SET description = EXCLUDED.description;

-- Link fish ↔ alleles
INSERT INTO public.fish_transgene_alleles (fish_id, transgene_base_code, allele_number)
SELECT f.id, l.transgene_base_code, l.allele_number
FROM (
  SELECT lower(trim(fish_code))           AS fish_code,
         lower(trim(transgene_base_code)) AS transgene_base_code,
         lower(trim(allele_number))       AS allele_number
  FROM core_fish_transgene_alleles_csv
  WHERE COALESCE(trim(fish_code),'') <> ''
    AND COALESCE(trim(transgene_base_code),'') <> ''
    AND COALESCE(trim(allele_number),'') <> ''
) l
JOIN public.fish f              ON f.fish_code = l.fish_code
JOIN public.transgene_alleles a ON a.transgene_base_code = l.transgene_base_code
                               AND a.allele_number       = l.allele_number
ON CONFLICT (fish_id, transgene_base_code, allele_number) DO NOTHING;

COMMIT;

\echo
\echo == summary ==
SELECT 'fish'                       AS table, COUNT(*) FROM public.fish
UNION ALL SELECT 'transgenes',             COUNT(*) FROM public.transgenes
UNION ALL SELECT 'transgene_alleles',      COUNT(*) FROM public.transgene_alleles
UNION ALL SELECT 'fish_transgene_alleles', COUNT(*) FROM public.fish_transgene_alleles
ORDER BY 1;