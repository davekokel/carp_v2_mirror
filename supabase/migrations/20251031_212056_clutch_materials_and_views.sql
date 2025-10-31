-- Generic link table for clutch ↔ materials, plus unified materials view.
-- Keeps v_clutch_treatments contract by aggregating from the new link.

CREATE EXTENSION IF NOT EXISTS pgcrypto;

-- 0) Unified materials registry view (start with plasmids; include RNAs if present)
CREATE OR REPLACE VIEW public.v_materials AS
SELECT 'plasmid'::text AS material_type, p.code::text AS material_code, p.name::text AS material_name
FROM public.plasmids p
UNION ALL
SELECT 'rna'::text AS material_type, r.code::text AS material_code, r.name::text AS material_name
FROM pg_catalog.pg_views v
JOIN LATERAL (
  SELECT * FROM public.v_rna_plasmids
) r ON v.schemaname='public' AND v.viewname='v_rna_plasmids';

-- 1) Generic link table
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='clutch_materials'
  ) THEN
    EXECUTE $CT$
      CREATE TABLE public.clutch_materials (
        id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        clutch_instance_id uuid NOT NULL
          REFERENCES public.clutch_instances(id) ON DELETE CASCADE,
        material_type      text NOT NULL,
        material_code      text NOT NULL,
        material_name      text,   -- optional display override
        notes              text,
        created_by         text,
        created_at         timestamptz NOT NULL DEFAULT now()
      )
    $CT$;
  END IF;

  -- ensure columns exist (defensive)
  PERFORM 1
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='clutch_materials' AND column_name='material_name';
  IF NOT FOUND THEN EXECUTE 'ALTER TABLE public.clutch_materials ADD COLUMN material_name text'; END IF;

  PERFORM 1
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='clutch_materials' AND column_name='notes';
  IF NOT FOUND THEN EXECUTE 'ALTER TABLE public.clutch_materials ADD COLUMN notes text'; END IF;

  PERFORM 1
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='clutch_materials' AND column_name='created_by';
  IF NOT FOUND THEN EXECUTE 'ALTER TABLE public.clutch_materials ADD COLUMN created_by text'; END IF;

  PERFORM 1
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='clutch_materials' AND column_name='created_at';
  IF NOT FOUND THEN EXECUTE 'ALTER TABLE public.clutch_materials ADD COLUMN created_at timestamptz NOT NULL DEFAULT now()'; END IF;

  -- uniqueness & indexes
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='uq_clutch_material') THEN
    EXECUTE $UX$
      CREATE UNIQUE INDEX uq_clutch_material
      ON public.clutch_materials (
        clutch_instance_id,
        lower(coalesce(material_type,'')),
        lower(coalesce(material_code,''))
      )
    $UX$;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='ix_clutch_materials_instance') THEN
    EXECUTE 'CREATE INDEX ix_clutch_materials_instance ON public.clutch_materials (clutch_instance_id)';
  END IF;
END
$$;

-- 2) Validate link rows against v_materials (soft FK via trigger)
CREATE OR REPLACE FUNCTION public.clutch_materials_validate()
RETURNS trigger
LANGUAGE plpgsql AS $$
DECLARE ok int;
BEGIN
  SELECT 1 INTO ok
  FROM public.v_materials vm
  WHERE lower(vm.material_type) = lower(NEW.material_type)
    AND lower(vm.material_code) = lower(NEW.material_code)
  LIMIT 1;

  IF ok IS NULL THEN
    RAISE EXCEPTION 'Unknown material (% %, for clutch %)', NEW.material_type, NEW.material_code, NEW.clutch_instance_id;
  END IF;

  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_clutch_materials_validate ON public.clutch_materials;
CREATE TRIGGER trg_clutch_materials_validate
BEFORE INSERT OR UPDATE ON public.clutch_materials
FOR EACH ROW
EXECUTE FUNCTION public.clutch_materials_validate();

-- 3) Rebuild v_clutch_treatments to aggregate from clutch_materials
CREATE OR REPLACE VIEW public.v_clutch_treatments AS
WITH base AS (
  SELECT
    cm.clutch_instance_id,
    cm.created_at,
    COALESCE(cm.material_name, vm.material_name) AS material_name
  FROM public.clutch_materials cm
  LEFT JOIN public.v_materials vm
    ON lower(vm.material_type)=lower(cm.material_type)
   AND lower(vm.material_code)=lower(cm.material_code)
),
agg AS (
  SELECT
    b.clutch_instance_id,
    COUNT(*)::int                       AS treatments_count,
    string_agg(DISTINCT b.material_name, ' + ' ORDER BY b.material_name) AS treatments_pretty,
    MAX(b.created_at)                   AS last_treatment_at
  FROM base b
  GROUP BY b.clutch_instance_id
)
SELECT * FROM agg;

-- 4) Optional backfill from quarantined table, if present
DO $$
BEGIN
  IF EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema='trash_carp' AND table_name='clutch_instance_treatments'
  ) THEN
    EXECUTE $BF$
      INSERT INTO public.clutch_materials
        (clutch_instance_id, material_type, material_code, material_name, notes, created_by, created_at)
      SELECT
        cit.clutch_instance_id,
        COALESCE(NULLIF(trim(cit.material_type),''),'plasmid') AS material_type,
        COALESCE(NULLIF(trim(cit.material_code),''), cit.material_name) AS material_code,
        cit.material_name,
        cit.notes,
        cit.created_by,
        COALESCE(cit.created_at, now())
      FROM trash_carp.clutch_instance_treatments cit
      ON CONFLICT (clutch_instance_id,
                   lower(coalesce(material_type,'')),
                   lower(coalesce(material_code,'')))
      DO NOTHING
    $BF$;
  END IF;
END
$$;
