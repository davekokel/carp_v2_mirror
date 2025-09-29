-- === Sequences & helper functions ==========================================
CREATE SEQUENCE IF NOT EXISTS public.auto_fish_seq;

CREATE OR REPLACE FUNCTION public.next_auto_fish_code()
RETURNS text LANGUAGE sql AS $$
  SELECT 'FSH-' || to_char(now(), 'YYYY') || '-' ||
         to_char(nextval('public.auto_fish_seq'), 'FM000');
$$;

CREATE SEQUENCE IF NOT EXISTS public.tank_label_seq;

CREATE OR REPLACE FUNCTION public.next_tank_code(p_prefix text)
RETURNS text LANGUAGE plpgsql AS $func$
DECLARE n bigint;
BEGIN
  n := nextval('public.tank_label_seq');
  RETURN p_prefix || to_char(n, 'FM000');
END
$func$;

-- === Fish table shape (idempotent) =========================================
ALTER TABLE public.fish
  ADD COLUMN IF NOT EXISTS batch_label text,
  ADD COLUMN IF NOT EXISTS line_building_stage text,
  ADD COLUMN IF NOT EXISTS nickname text,
  ADD COLUMN IF NOT EXISTS description text,
  ADD COLUMN IF NOT EXISTS strain text,
  ADD COLUMN IF NOT EXISTS date_of_birth date,
  ADD COLUMN IF NOT EXISTS auto_fish_code text;

-- Optional: format hygiene for auto_fish_code (FSH-YYYY-###)
DO $$
BEGIN
  IF to_regclass('public.v_fish_overview_v1') IS NOT NULL THEN
    EXECUTE 'GRANT SELECT ON public.v_fish_overview_v1 TO anon, authenticated';
  END IF;
  IF to_regclass('public.fish') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.fish TO anon, authenticated'; END IF;
  IF to_regclass('public.transgenes') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.transgenes TO anon, authenticated'; END IF;
  IF to_regclass('public.fish_transgene_alleles') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.fish_transgene_alleles TO anon, authenticated'; END IF;
  IF to_regclass('public.treatments') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.treatments TO anon, authenticated'; END IF;
  IF to_regclass('public.fish_treatments') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.fish_treatments TO anon, authenticated'; END IF;
  IF to_regclass('public.tank_assignments') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.tank_assignments TO anon, authenticated'; END IF;
  IF to_regclass('public.transgene_allele_catalog') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.transgene_allele_catalog TO anon, authenticated'; END IF;
END$$;

-- === Indexes ===============================================================
CREATE EXTENSION IF NOT EXISTS pg_trgm;

CREATE INDEX IF NOT EXISTS ix_fish_name_trgm
  ON public.fish USING gin (name gin_trgm_ops);

CREATE INDEX IF NOT EXISTS ix_fta_fish ON public.fish_transgene_alleles(fish_id);
CREATE INDEX IF NOT EXISTS ix_fta_transgene ON public.fish_transgene_alleles(transgene_base_code);
CREATE INDEX IF NOT EXISTS ix_ft_fish ON public.fish_treatments(fish_id);
CREATE INDEX IF NOT EXISTS ix_treatments_performed_at ON public.treatments(performed_at);

-- === View (stable shape for UI) ============================================
CREATE OR REPLACE VIEW public.v_fish_overview_v1 AS
WITH tg AS (
  SELECT fta.fish_id,
         string_agg(DISTINCT t.transgene_base_code, ', ' ORDER BY t.transgene_base_code) AS transgenes
  FROM public.fish_transgene_alleles fta
  JOIN public.transgenes t ON t.transgene_base_code = fta.transgene_base_code
  GROUP BY fta.fish_id
),
alle AS (
  SELECT x.fish_id,
         string_agg(DISTINCT x.allele_label, ', ' ORDER BY x.allele_label) AS alleles
  FROM (
    SELECT fta.fish_id,
           trim(CONCAT(
             fta.transgene_base_code,
             CASE WHEN NULLIF(fta.allele_number,'') IS NOT NULL
                  THEN '('||fta.allele_number||')' ELSE '' END
           )) AS allele_label
    FROM public.fish_transgene_alleles fta
  ) x
  GROUP BY x.fish_id
),
tx AS (
  SELECT ft.fish_id,
         count(DISTINCT ft.treatment_id) AS n_treatments,
         max(t.performed_at)::date       AS last_treatment_on
  FROM public.fish_treatments ft
  JOIN public.treatments t ON t.id = ft.treatment_id
  GROUP BY ft.fish_id
)
SELECT
  f.id,
  f.name                           AS fish_name,
  f.auto_fish_code                 AS auto_fish_code,
  f.batch_label                    AS batch,
  f.line_building_stage            AS line_building_stage,
  f.nickname,
  f.date_of_birth,
  f.description,
  COALESCE(tg.transgenes,'')       AS transgenes,
  COALESCE(alle.alleles,'')        AS alleles,
  COALESCE(tx.n_treatments,0)      AS n_treatments,
  tx.last_treatment_on
FROM public.fish f
LEFT JOIN tg   ON tg.fish_id   = f.id
LEFT JOIN alle ON alle.fish_id = f.id
LEFT JOIN tx   ON tx.fish_id   = f.id;

-- === Grants (adjust if RLS on) =============================================
GRANT SELECT ON public.v_fish_overview_v1 TO anon, authenticated;
DO $$
BEGIN
  IF to_regclass('public.v_fish_overview_v1') IS NOT NULL THEN
    EXECUTE 'GRANT SELECT ON public.v_fish_overview_v1 TO anon, authenticated';
  END IF;
  IF to_regclass('public.fish') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.fish TO anon, authenticated'; END IF;
  IF to_regclass('public.transgenes') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.transgenes TO anon, authenticated'; END IF;
  IF to_regclass('public.fish_transgene_alleles') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.fish_transgene_alleles TO anon, authenticated'; END IF;
  IF to_regclass('public.treatments') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.treatments TO anon, authenticated'; END IF;
  IF to_regclass('public.fish_treatments') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.fish_treatments TO anon, authenticated'; END IF;
  IF to_regclass('public.tank_assignments') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.tank_assignments TO anon, authenticated'; END IF;
  IF to_regclass('public.transgene_allele_catalog') IS NOT NULL THEN EXECUTE 'GRANT SELECT ON public.transgene_allele_catalog TO anon, authenticated'; END IF;
END$$;
