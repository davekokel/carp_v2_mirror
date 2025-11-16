BEGIN;

-- 1) Create the join table if missing
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.tables
    WHERE table_schema='public' AND table_name='join_treatment_dyes'
  ) THEN
    CREATE TABLE public.join_treatment_dyes (
      id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
      treatment_id  uuid NOT NULL,
      dye_id        uuid NOT NULL,
      amount_text   text,         -- e.g., "2 µL", "10 mg/mL"
      conc_text     text,         -- optional concentration
      notes         text,
      created_at    timestamptz NOT NULL DEFAULT now()
    );
  END IF;
END$$;

-- 2) FKs (safe if they already exist)
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jtd_treatment') THEN
    ALTER TABLE public.join_treatment_dyes
      ADD CONSTRAINT fk_jtd_treatment
      FOREIGN KEY (treatment_id)
      REFERENCES public.treatments(id)
      ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
    ALTER TABLE public.join_treatment_dyes VALIDATE CONSTRAINT fk_jtd_treatment;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jtd_dye') THEN
    ALTER TABLE public.join_treatment_dyes
      ADD CONSTRAINT fk_jtd_dye
      FOREIGN KEY (dye_id)
      REFERENCES public.dyes(id)
      ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
    ALTER TABLE public.join_treatment_dyes VALIDATE CONSTRAINT fk_jtd_dye;
  END IF;
END$$;

-- 3) Uniqueness + look-up indexes
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='uq_jtd_treatment_dye') THEN
    ALTER TABLE public.join_treatment_dyes
      ADD CONSTRAINT uq_jtd_treatment_dye UNIQUE (treatment_id, dye_id);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='ix_jtd_treatment') THEN
    CREATE INDEX ix_jtd_treatment ON public.join_treatment_dyes(treatment_id);
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_indexes WHERE schemaname='public' AND indexname='ix_jtd_dye') THEN
    CREATE INDEX ix_jtd_dye ON public.join_treatment_dyes(dye_id);
  END IF;
END$$;

COMMIT;
