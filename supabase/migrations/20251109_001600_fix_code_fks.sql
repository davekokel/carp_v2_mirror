BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_dyes_code                   ON public.dyes(dye_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fluors_code                 ON public.fluors(fluor_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_tags_code                   ON public.tags(tag_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fusions_code                ON public.fusions(fusion_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_transgenes_base_code        ON public.transgenes(transgene_base_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_plasmids_code               ON public.plasmids(code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_rnas_code                   ON public.rnas(rna_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_treatments_code             ON public.treatments(treat_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_treatments_chemical_code    ON public.treatments_chemical(ct_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_treatments_fluorescent_code ON public.treatments_fluorescent(ft_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_treatments_physical_code    ON public.treatments_physical(pt_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_fish_code                   ON public.fish(fish_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_tanks_code                  ON public.tanks(tank_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_tank_pairs_code             ON public.tank_pairs(tank_pair_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_plates_code                 ON public.plates(plate_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_treated_clutches_code       ON public.treated_clutches(treated_clutch_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_clutch_instances_code       ON public.clutch_instances(clutch_instance_code);
CREATE UNIQUE INDEX IF NOT EXISTS uq_crosses_run_code            ON public.crosses(cross_run_code);

CREATE INDEX IF NOT EXISTS idx_plate_slots_fish_code  ON public.plate_slots(fish_code);
CREATE INDEX IF NOT EXISTS idx_crosses_tank_pair_code ON public.crosses(tank_pair_code);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_plate_slots_fish_code'
      AND conrelid='public.plate_slots'::regclass
  ) THEN
    ALTER TABLE public.plate_slots
      ADD CONSTRAINT fk_plate_slots_fish_code
      FOREIGN KEY (fish_code) REFERENCES public.fish(fish_code)
      ON UPDATE RESTRICT ON DELETE RESTRICT
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_crosses_tank_pair_code'
      AND conrelid='public.crosses'::regclass
  ) THEN
    ALTER TABLE public.crosses
      ADD CONSTRAINT fk_crosses_tank_pair_code
      FOREIGN KEY (tank_pair_code) REFERENCES public.tank_pairs(tank_pair_code)
      ON UPDATE RESTRICT ON DELETE RESTRICT
      DEFERRABLE INITIALLY DEFERRED
      NOT VALID;
  END IF;
END$$;

COMMIT;
