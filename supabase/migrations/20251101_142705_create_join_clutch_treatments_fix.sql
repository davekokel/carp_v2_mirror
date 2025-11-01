BEGIN;

CREATE TABLE IF NOT EXISTS public.join_clutch_treatments (
  id                 uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_instance_id uuid NOT NULL REFERENCES public.clutch_instances(id) ON DELETE CASCADE,
  treatment_type     text NOT NULL,   -- 'plasmid' | 'rna' | other
  treatment_code     text NOT NULL,   -- e.g. pDQM005
  treatment_name     text,            -- friendly label snapshot
  notes              text,
  created_by         text,
  created_at         timestamptz NOT NULL DEFAULT now()
);

COMMENT ON TABLE public.join_clutch_treatments IS
  'Join table linking clutch_instances to applied treatments (plasmids, RNAs, etc).';

-- Helper index
CREATE INDEX IF NOT EXISTS idx_join_clutch_treatments_clutch_instance_id
  ON public.join_clutch_treatments (clutch_instance_id);

-- Expression-based UNIQUE needs to be a unique index (not a table constraint)
CREATE UNIQUE INDEX IF NOT EXISTS uq_join_clutch_treatments
  ON public.join_clutch_treatments (
    clutch_instance_id,
    lower(btrim(coalesce(treatment_type, ''))),
    lower(btrim(coalesce(treatment_code, '')))
  );

COMMIT;
