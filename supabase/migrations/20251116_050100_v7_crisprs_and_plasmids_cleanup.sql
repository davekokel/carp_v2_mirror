BEGIN;

CREATE TABLE IF NOT EXISTS public.crisprs (
  id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  crispr_code  text UNIQUE NOT NULL,
  target_locus text,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS public.join_treatment_crisprs (
  treatment_id uuid NOT NULL,
  crispr_id    uuid NOT NULL,
  amount       text,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_join_treatment_crisprs PRIMARY KEY (treatment_id, crispr_id),
  CONSTRAINT fk_jtc_treatment
    FOREIGN KEY (treatment_id)
    REFERENCES public.treatments(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_jtc_crispr
    FOREIGN KEY (crispr_id)
    REFERENCES public.crisprs(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_jtc_treatment_id
  ON public.join_treatment_crisprs (treatment_id);

CREATE INDEX IF NOT EXISTS idx_jtc_crispr_id
  ON public.join_treatment_crisprs (crispr_id);

ALTER TABLE public.plasmids
  ALTER COLUMN plasmid_base_code SET NOT NULL;

CREATE UNIQUE INDEX IF NOT EXISTS uq_plasmids_plasmid_base_code
  ON public.plasmids (plasmid_base_code);

COMMIT;
