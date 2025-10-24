BEGIN;

-- 3a) Drop old canonical view (safe now: no DB view depends on it)
DROP VIEW IF EXISTS public.v_tank_pairs;

-- 3b) Create canonical enriched v_tank_pairs (explicit, same legacy order + pretty fields)
CREATE VIEW public.v_tank_pairs AS
WITH lc AS (
  SELECT
    c.fish_pair_id,
    c.clutch_code,
    c.expected_genotype,
    ROW_NUMBER() OVER (PARTITION BY c.fish_pair_id ORDER BY c.created_at DESC NULLS LAST) AS rn
  FROM public.clutches c
)
SELECT
  tp.id,
  tp.tank_pair_code,
  tp.tp_seq,
  tp.status,
  tp.role_orientation,
  tp.concept_id,
  tp.fish_pair_id,
  tp.created_by,
  tp.created_at,
  tp.updated_at,

  mt.tank_id                               AS mother_tank_id,
  COALESCE(tp.mom_tank_code, mt.tank_code) AS mom_tank_code,
  mt.fish_code                              AS mom_fish_code,
  tp.mom_genotype,

  dt.tank_id                               AS father_tank_id,
  COALESCE(tp.dad_tank_code, dt.tank_code) AS dad_tank_code,
  dt.fish_code                              AS dad_fish_code,
  tp.dad_genotype,

  -- appended pretty helpers
  COALESCE(mt.fish_code,'') || ' × ' || COALESCE(dt.fish_code,'') AS pair_fish,
  COALESCE(tp.mom_tank_code, mt.tank_code) || ' × ' ||
  COALESCE(tp.dad_tank_code, dt.tank_code)                         AS pair_tanks,

  CASE
    WHEN COALESCE(lc.expected_genotype,'') <> '' THEN lc.expected_genotype
    WHEN COALESCE(tp.mom_genotype,'') <> '' AND COALESCE(tp.dad_genotype,'') <> ''
         THEN tp.mom_genotype || ' × ' || tp.dad_genotype
    ELSE NULLIF(tp.mom_genotype,'')
  END AS pair_genotype,

  -- stable alias for UI/filters
  CASE
    WHEN COALESCE(lc.expected_genotype,'') <> '' THEN lc.expected_genotype
    WHEN COALESCE(tp.mom_genotype,'') <> '' AND COALESCE(tp.dad_genotype,'') <> ''
         THEN tp.mom_genotype || ' × ' || tp.dad_genotype
    ELSE NULLIF(tp.mom_genotype,'')
  END AS genotype,

  lc.clutch_code

FROM public.tank_pairs tp
LEFT JOIN public.tanks mt ON mt.tank_id = tp.mother_tank_id
LEFT JOIN public.tanks dt ON dt.tank_id = tp.father_tank_id
LEFT JOIN lc ON lc.fish_pair_id = tp.fish_pair_id AND lc.rn = 1
ORDER BY tp.created_at DESC NULLS LAST;

COMMENT ON VIEW public.v_tank_pairs IS
  'Snapshot-aware tank pairs, legacy columns + UI helpers: pair_fish, pair_tanks, pair_genotype, genotype, clutch_code.';

COMMIT;

-- 3c) Rebind dependents from v2 back to canonical v_tank_pairs
DO $$
DECLARE
  rec RECORD;
  def text;
  newdef text;
BEGIN
  FOR rec IN
    SELECT n.nspname AS schemaname, c.relname AS viewname, pg_get_viewdef(c.oid, true) AS def
    FROM   pg_depend d
    JOIN   pg_rewrite   r ON r.oid = d.objid
    JOIN   pg_class     c ON c.oid = r.ev_class AND c.relkind = 'v'
    JOIN   pg_namespace n ON n.oid = c.relnamespace
    WHERE  d.refclassid='pg_class'::regclass
       AND d.refobjid   ='public.v_tank_pairs_v2'::regclass
  LOOP
    newdef := replace(rec.def, 'public.v_tank_pairs_v2', 'public.v_tank_pairs');
    newdef := regexp_replace(newdef, '(^|[^A-Za-z0-9_])v_tank_pairs_v2([^A-Za-z0-9_])', '\1public.v_tank_pairs\2', 'g');

    EXECUTE 'CREATE OR REPLACE VIEW '
            || quote_ident(rec.schemaname) || '.' || quote_ident(rec.viewname)
            || E'\nAS\n' || newdef;
  END LOOP;
END
$$;

-- 3d) Drop the temporary v2 view
DROP VIEW IF EXISTS public.v_tank_pairs_v2;
