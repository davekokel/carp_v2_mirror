CREATE TABLE IF NOT EXISTS public.join_treatment_plasmids (
  treatment_id uuid NOT NULL,
  plasmid_id   uuid NOT NULL,
  amount_pg    numeric,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_join_treatment_plasmids PRIMARY KEY (treatment_id, plasmid_id),
  CONSTRAINT fk_jtpl_treatment
    FOREIGN KEY (treatment_id) REFERENCES public.treatments(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_jtpl_plasmid
    FOREIGN KEY (plasmid_id)   REFERENCES public.plasmids(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS public.join_treatment_rnas (
  treatment_id uuid NOT NULL,
  rna_id       uuid NOT NULL,
  amount_pg    numeric,
  notes        text,
  created_at   timestamptz NOT NULL DEFAULT now(),
  CONSTRAINT pk_join_treatment_rnas PRIMARY KEY (treatment_id, rna_id),
  CONSTRAINT fk_jtr_treatment
    FOREIGN KEY (treatment_id) REFERENCES public.treatments(id)
    ON UPDATE CASCADE ON DELETE CASCADE,
  CONSTRAINT fk_jtr_rna
    FOREIGN KEY (rna_id)       REFERENCES public.rnas(id)
    ON UPDATE CASCADE ON DELETE CASCADE
);
