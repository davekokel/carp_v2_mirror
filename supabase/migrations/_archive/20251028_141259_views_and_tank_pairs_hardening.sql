BEGIN;

-- 1) Recreate views cleanly (avoid “drop columns from view” issues)
DROP VIEW IF EXISTS public.v_tanks CASCADE;
DROP VIEW IF EXISTS public.v_tank_pairs CASCADE;

CREATE VIEW public.v_tanks
(tank_uuid, tank_code, status, created_at, fish_code, fish_uuid, started_at, ended_at, is_active) AS
SELECT
  t.tank_uuid::uuid,
  t.tank_code::text,
  t.status::text,
  t.created_at::timestamptz,
  f.fish_code::text,
  f.fish_uuid::uuid,
  m.joined_at::timestamptz,
  m.left_at::timestamptz,
  (m.left_at IS NULL)
FROM public.fish_tank_memberships m
JOIN public.tanks t ON t.tank_uuid = m.tank_uuid AND t.status = 'active'
JOIN public.fish  f ON f.fish_uuid = m.fish_uuid
WHERE m.left_at IS NULL;

CREATE OR REPLACE VIEW public.v_fish_rich AS
WITH tcounts AS (
  SELECT v.fish_code::text AS fish_code, COUNT(*)::int AS n_active_tanks
  FROM public.v_tanks v
  GROUP BY v.fish_code
), alleles AS (
  SELECT
    f.fish_uuid,
    f.fish_code::text                 AS fish_code,
    fta.transgene_base_code           AS transgene_base_code,
    fta.allele_number                 AS allele_number,
    ta.allele_nickname::text          AS allele_nickname,
    ('gu' || fta.allele_number::text) AS allele_code,
    ('Tg(' || fta.transgene_base_code || ')' || ('gu' || fta.allele_number::text)) AS transgene_pretty
  FROM public.fish f
  LEFT JOIN public.fish_transgene_alleles fta ON fta.fish_uuid = f.fish_uuid
  LEFT JOIN public.transgene_alleles ta ON ta.transgene_base_code = fta.transgene_base_code AND ta.allele_number = fta.allele_number
), geno AS (
  SELECT a.fish_uuid, string_agg(a.transgene_pretty, '; ' ORDER BY a.transgene_pretty)::text AS genotype_rollup
  FROM alleles a
  GROUP BY a.fish_uuid
)
SELECT
  f.fish_uuid::uuid                 AS fish_uuid,
  f.fish_code::text                 AS fish_code,
  (CASE WHEN f.fish_name IS NOT NULL THEN f.fish_name ELSE f.name END)::text       AS fish_name,
  (CASE WHEN f.fish_nickname IS NOT NULL THEN f.fish_nickname ELSE f.nickname END)::text AS fish_nickname,
  f.genetic_background::text        AS genetic_background,
  f.line_building_stage::text       AS line_building_stage,
  f.date_birth::date                AS date_birth,
  a.allele_number                   AS allele_number,
  a.allele_code::text               AS allele_code,
  tcounts.n_active_tanks            AS n_active_tanks,
  a.transgene_pretty::text          AS transgene_pretty,
  g.genotype_rollup::text           AS genotype_rollup,
  f.created_at::timestamptz         AS created_at
FROM public.fish f
LEFT JOIN alleles a  ON a.fish_uuid  = f.fish_uuid
LEFT JOIN tcounts    ON tcounts.fish_code = f.fish_code
LEFT JOIN geno g     ON g.fish_uuid  = f.fish_uuid
ORDER BY f.fish_code, a.transgene_pretty NULLS LAST;

CREATE VIEW public.v_tank_pairs
(tank_pair_code, fish_pair_code, mom_fish_code, dad_fish_code, mother_tank_code, father_tank_code, status, created_at) AS
SELECT
  tp.tank_pair_code,
  tp.fish_pair_code,
  fm.fish_code,
  fd.fish_code,
  tm.tank_code,
  tf.tank_code,
  tp.status,
  tp.created_at
FROM public.tank_pairs tp
LEFT JOIN public.fish_pairs fp ON fp.fish_pair_code = tp.fish_pair_code
LEFT JOIN public.fish fm ON fm.fish_uuid = fp.mom_fish_id
LEFT JOIN public.fish fd ON fd.fish_uuid = fp.dad_fish_id
LEFT JOIN public.tanks tm ON tm.tank_uuid = tp.mother_tank_id
LEFT JOIN public.tanks tf ON tf.tank_uuid = tp.father_tank_id;

-- 2) Guarded NOT NULL on tank_pairs.fish_pair_code (don’t block if NULLs exist)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM public.tank_pairs WHERE fish_pair_code IS NULL) THEN
    EXECUTE 'ALTER TABLE public.tank_pairs ALTER COLUMN fish_pair_code SET NOT NULL';
  ELSE
    RAISE NOTICE 'Skipped SET NOT NULL: tank_pairs has NULL fish_pair_code';
  END IF;
END $$;

-- 3) Trigger to enforce non-NULL fish_pair_code on writes
CREATE OR REPLACE FUNCTION public.trg_tank_pairs_require_fp()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.fish_pair_code IS NULL THEN
    RAISE EXCEPTION 'tank_pairs.fish_pair_code must not be NULL';
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS tank_pairs_require_fp ON public.tank_pairs;
CREATE TRIGGER tank_pairs_require_fp
BEFORE INSERT OR UPDATE ON public.tank_pairs
FOR EACH ROW EXECUTE FUNCTION public.trg_tank_pairs_require_fp();

-- 4) Unique index + UNIQUE constraint on fish_pairs(fish_pair_code), safely
DO $$
BEGIN
  IF EXISTS (
    SELECT fish_pair_code
    FROM public.fish_pairs
    WHERE fish_pair_code IS NOT NULL
    GROUP BY fish_pair_code
    HAVING COUNT(*) > 1
  ) THEN
    RAISE NOTICE 'Skipped UNIQUE: duplicate fish_pair_code values exist';
  ELSE
    IF EXISTS (
      SELECT 1
      FROM pg_class c
      JOIN pg_namespace n ON n.oid = c.relnamespace
      WHERE n.nspname = 'public' AND c.relname = 'uq_fish_pairs_code'
    ) THEN
      IF EXISTS (
        SELECT 1
        FROM pg_index idx
        JOIN pg_class ic ON ic.oid = idx.indexrelid
        JOIN pg_namespace ns ON ns.oid = ic.relnamespace
        WHERE ns.nspname='public' AND ic.relname='uq_fish_pairs_code' AND idx.indpred IS NOT NULL
      ) THEN
        DROP INDEX IF EXISTS public.uq_fish_pairs_code;
      END IF;
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='uq_fish_pairs_code'
    ) THEN
      CREATE UNIQUE INDEX uq_fish_pairs_code ON public.fish_pairs(fish_pair_code);
    END IF;

    IF NOT EXISTS (
      SELECT 1 FROM pg_constraint WHERE conname='con_uq_fish_pairs_code'
    ) THEN
      ALTER TABLE public.fish_pairs ADD CONSTRAINT con_uq_fish_pairs_code UNIQUE USING INDEX uq_fish_pairs_code;
    END IF;
  END IF;
END $$;

-- 5) FK from tank_pairs(fish_pair_code) → fish_pairs(fish_pair_code), only if UNIQUE exists
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conname='con_uq_fish_pairs_code')
     AND NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_tank_pairs_fish_pair_code') THEN
    ALTER TABLE public.tank_pairs
      ADD CONSTRAINT fk_tank_pairs_fish_pair_code
      FOREIGN KEY (fish_pair_code)
      REFERENCES public.fish_pairs(fish_pair_code)
      ON DELETE RESTRICT
      DEFERRABLE INITIALLY DEFERRED;
  ELSE
    RAISE NOTICE 'Skipped FK: missing UNIQUE on fish_pairs(fish_pair_code) or FK already exists';
  END IF;
END $$;

COMMIT;