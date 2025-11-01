BEGIN;

CREATE TABLE public.join_clutch_treatments (
  id                      uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  clutch_instance_id      uuid NOT NULL REFERENCES public.clutch_instances(id) ON DELETE CASCADE,
  treatment_type          text NOT NULL,  -- 'plasmid', 'rna', or other
  treatment_code          text NOT NULL,  -- e.g. pDQM005
  treatment_name          text,           -- human-friendly name
  notes                   text,
  created_by              text,
  created_at              timestamptz DEFAULT now(),

  CONSTRAINT uq_join_clutch_treatments UNIQUE (
    clutch_instance_id,
    lower(btrim(coalesce(treatment_type, ''))),
    lower(btrim(coalesce(treatment_code, '')))
  )
);

COMMENT ON TABLE public.join_clutch_treatments IS
  'Join table linking clutch_instances to applied treatments (plasmids, RNAs, etc).';

CREATE INDEX idx_join_clutch_treatments_clutch_instance_id
  ON public.join_clutch_treatments (clutch_instance_id);

COMMIT;
