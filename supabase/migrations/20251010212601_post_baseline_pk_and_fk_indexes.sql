DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.fish'::regclass AND contype='p'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD PRIMARY KEY (id_uuid)';
  END IF;
END
$$ LANGUAGE plpgsql;

ALTER TABLE public.fish_seed_batches_map
  ADD COLUMN IF NOT EXISTS id uuid DEFAULT gen_random_uuid();
DO 28762
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conrelid='public.fish_seed_batches_map'::regclass AND contype='p'
  ) THEN
    EXECUTE 'ALTER TABLE public.fish_seed_batches_map ADD PRIMARY KEY (id)';
  END IF;
END
$$ LANGUAGE plpgsql;
DO 28762
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='uq_fsbm_natural' AND conrelid='public.fish_seed_batches_map'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.fish_seed_batches_map ADD CONSTRAINT uq_fsbm_natural UNIQUE (fish_id, seed_batch_id)';
  END IF;
END
$$ LANGUAGE plpgsql;
DO 28762
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname='fk_fsbm_fish' AND conrelid='public.fish_seed_batches_map'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.fish_seed_batches_map
             ADD CONSTRAINT fk_fsbm_fish
             FOREIGN KEY (fish_id) REFERENCES public.fish(id_uuid)
             ON DELETE CASCADE NOT VALID';
    EXECUTE 'ALTER TABLE public.fish_seed_batches_map VALIDATE CONSTRAINT fk_fsbm_fish';
  END IF;
END
$$ LANGUAGE plpgsql;

CREATE INDEX IF NOT EXISTS idx_clutch_containers_container_id              ON public.clutch_containers(container_id);
CREATE INDEX IF NOT EXISTS idx_clutch_containers_source_container_id       ON public.clutch_containers(source_container_id);
CREATE INDEX IF NOT EXISTS idx_clutch_plan_treatments_clutch_id            ON public.clutch_plan_treatments(clutch_id);
CREATE INDEX IF NOT EXISTS idx_clutches_cross_instance_id                  ON public.clutches(cross_instance_id);
CREATE INDEX IF NOT EXISTS idx_containers_request_id                       ON public.containers(request_id);
CREATE INDEX IF NOT EXISTS idx_cross_instances_cross_id                    ON public.cross_instances(cross_id);
CREATE INDEX IF NOT EXISTS idx_cross_instances_father_tank_id              ON public.cross_instances(father_tank_id);
CREATE INDEX IF NOT EXISTS idx_cross_instances_mother_tank_id              ON public.cross_instances(mother_tank_id);
CREATE INDEX IF NOT EXISTS idx_cross_plan_genotype_alleles_base_allele     ON public.cross_plan_genotype_alleles(transgene_base_code, allele_number);
CREATE INDEX IF NOT EXISTS idx_cross_plan_runs_tank_a_id                   ON public.cross_plan_runs(tank_a_id);
CREATE INDEX IF NOT EXISTS idx_cross_plan_runs_tank_b_id                   ON public.cross_plan_runs(tank_b_id);
CREATE INDEX IF NOT EXISTS idx_fish_seed_batches_fish_id                   ON public.fish_seed_batches(fish_id);
CREATE INDEX IF NOT EXISTS idx_fish_transgene_alles_base_allele            ON public.fish_transgene_alleles(transgene_base_code, allele_number);
CREATE INDEX IF NOT EXISTS idx_planned_crosses_cross_id                    ON public.planned_crosses(cross_id);
CREATE INDEX IF NOT EXISTS idx_planned_crosses_cross_instance_id           ON public.planned_crosses(cross_instance_id);
CREATE INDEX IF NOT EXISTS idx_planned_crosses_father_tank_id              ON public.planned_crosses(father_tank_id);
CREATE INDEX IF NOT EXISTS idx_planned_crosses_mother_tank_id              ON public.planned_crosses(mother_tank_id);
CREATE INDEX IF NOT EXISTS idx_tank_requests_fish_id                        ON public.tank_requests(fish_id);
