BEGIN;

CREATE INDEX IF NOT EXISTS idx_clutch_instances_tank_pair_code ON public.clutch_instances(tank_pair_code);
CREATE INDEX IF NOT EXISTS idx_rnas_base_plasmid_code         ON public.rnas(base_plasmid_code);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_clutch_instances_tank_pair_code'
      AND conrelid='public.clutch_instances'::regclass
  ) THEN
    ALTER TABLE public.clutch_instances
      ADD CONSTRAINT fk_clutch_instances_tank_pair_code
      FOREIGN KEY (tank_pair_code) REFERENCES public.tank_pairs(tank_pair_code)
      ON UPDATE RESTRICT ON DELETE RESTRICT
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_rnas_base_plasmid_code'
      AND conrelid='public.rnas'::regclass
  ) THEN
    ALTER TABLE public.rnas
      ADD CONSTRAINT fk_rnas_base_plasmid_code
      FOREIGN KEY (base_plasmid_code) REFERENCES public.plasmids(code)
      ON UPDATE RESTRICT ON DELETE RESTRICT
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

COMMIT;
