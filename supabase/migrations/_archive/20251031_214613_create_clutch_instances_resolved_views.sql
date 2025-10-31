-- =============================================================================
-- v_clutch_instances_resolved (+ display_resolved)
-- Wrapper views that LEFT JOIN v_clutch_treatments to expose resolved treatment fields.
-- No base-table changes; keeps DB normalized and all pages consistent.
-- =============================================================================

-- Helpful index (no-op if present)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='ix_clutch_instances_code') THEN
    EXECUTE 'CREATE INDEX ix_clutch_instances_code ON public.clutch_instances (clutch_instance_code)';
  END IF;
END
$$;

-- Effective RESOLVED
CREATE OR REPLACE VIEW public.v_clutch_instances_resolved AS
WITH src AS (
  SELECT
    v.*,
    ci.id AS clutch_instance_uuid
  FROM public.v_clutch_instances_effective v
  JOIN public.clutch_instances ci
    ON ci.clutch_instance_code = v.clutch_code
)
SELECT
  s.*,
  COALESCE(vt.treatments_count_effective, 0)::int        AS treatments_count_effective_resolved,
  COALESCE(vt.treatments_pretty_effective, ''::text)      AS treatments_pretty_effective_resolved,
  CASE
    WHEN COALESCE(vt.treatments_pretty_effective,'') <> '' AND COALESCE(s.clutch_genotype_effective,'') <> ''
      THEN vt.treatments_pretty_effective || ' > ' || s.clutch_genotype_effective
    ELSE COALESCE(vt.treatments_pretty_effective, s.clutch_genotype_effective, ''::text)
  END                                                    AS treatments_genotype_effective_resolved,
  vt.last_treatment_at
FROM src s
LEFT JOIN public.v_clutch_treatments vt
  ON vt.clutch_instance_id = s.clutch_instance_uuid;

COMMENT ON VIEW public.v_clutch_instances_resolved IS
  'Resolved clutch instances: wrapper over v_clutch_instances_effective + v_clutch_treatments (count/pretty/genotype rollups).';

-- Display RESOLVED (only if display view exists)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.views
    WHERE table_schema='public' AND table_name='v_clutch_instances_display'
  ) THEN
    EXECUTE $$
      CREATE OR REPLACE VIEW public.v_clutch_instances_display_resolved AS
      WITH src AS (
        SELECT
          v.*,
          ci.id AS clutch_instance_uuid
        FROM public.v_clutch_instances_display v
        JOIN public.clutch_instances ci
          ON ci.clutch_instance_code = v.clutch_code
      )
      SELECT
        s.*,
        COALESCE(vt.treatments_count_effective, 0)::int        AS treatments_count_effective_resolved,
        COALESCE(vt.treatments_pretty_effective, ''::text)      AS treatments_pretty_effective_resolved,
        CASE
          WHEN COALESCE(vt.treatments_pretty_effective,'') <> '' AND COALESCE(s.clutch_genotype_pretty,'') <> ''
            THEN vt.treatments_pretty_effective || ' > ' || s.clutch_genotype_pretty
          ELSE COALESCE(vt.treatments_pretty_effective, s.clutch_genotype_pretty, ''::text)
        END                                                    AS treatments_genotype_effective_resolved,
        vt.last_treatment_at
      FROM src s
      LEFT JOIN public.v_clutch_treatments vt
        ON vt.clutch_instance_id = s.clutch_instance_uuid;
    $$;
    EXECUTE $$
      COMMENT ON VIEW public.v_clutch_instances_display_resolved IS
      'Resolved display: wrapper over v_clutch_instances_display + v_clutch_treatments (count/pretty/genotype rollups).';
    $$;
  END IF;
END
$$;

-- Optional: keep temporary  “_plus” aliases pointing at the resolved views (harmless if never used)
DO $$
BEGIN
  EXECUTE 'CREATE OR REPLACE VIEW public.v_clutch_instances_effective_plus AS SELECT * FROM public.v_clutch_instances_resolved';
  IF EXISTS (SELECT 1 FROM information_schema.views WHERE table_schema=''public'' AND table_name=''v_clutch_instances_display'') THEN
    EXECUTE 'CREATE OR REPLACE VIEW public.v_clutch_instances_display_plus AS SELECT * FROM public.v_clutch_instances_display_resolved';
  END IF;
END
$$;
