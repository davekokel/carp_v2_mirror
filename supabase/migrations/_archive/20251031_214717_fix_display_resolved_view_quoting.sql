-- Fix quoting inside DO block when creating v_clutch_instances_display_resolved.
DO $wrap$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.views
    WHERE table_schema='public' AND table_name='v_clutch_instances_display'
  ) THEN
    -- Use a different dollar-quote tag ($V$ ... $V$) so it doesn't terminate this DO block.
    EXECUTE $V$
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
        COALESCE(vt.treatments_count_effective, 0)::int         AS treatments_count_effective_resolved,
        COALESCE(vt.treatments_pretty_effective, ''::text)       AS treatments_pretty_effective_resolved,
        CASE
          WHEN COALESCE(vt.treatments_pretty_effective,'') <> '' AND COALESCE(s.clutch_genotype_pretty,'') <> ''
            THEN vt.treatments_pretty_effective || ' > ' || s.clutch_genotype_pretty
          ELSE COALESCE(vt.treatments_pretty_effective, s.clutch_genotype_pretty, ''::text)
        END                                                     AS treatments_genotype_effective_resolved,
        vt.last_treatment_at
      FROM src s
      LEFT JOIN public.v_clutch_treatments vt
        ON vt.clutch_instance_id = s.clutch_instance_uuid;
    $V$;

    EXECUTE $V$
      COMMENT ON VIEW public.v_clutch_instances_display_resolved IS
      'Resolved display: wrapper over v_clutch_instances_display + v_clutch_treatments (count/pretty/genotype rollups).';
    $V$;
  END IF;
END
$wrap$;
