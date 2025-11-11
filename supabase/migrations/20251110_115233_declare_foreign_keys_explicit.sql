BEGIN;

-- ===== Tanks / Tank pairs / Cross / Clutches =====
DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_tanks_location') THEN
    ALTER TABLE public.tanks
      ADD CONSTRAINT fk_tanks_location
      FOREIGN KEY (location_id) REFERENCES public.locations(id)
      ON UPDATE CASCADE ON DELETE SET NULL NOT VALID;
    ALTER TABLE public.tanks VALIDATE CONSTRAINT fk_tanks_location;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_tank_pairs_mother') THEN
    ALTER TABLE public.tank_pairs
      ADD CONSTRAINT fk_tank_pairs_mother
      FOREIGN KEY (mother_tank_id) REFERENCES public.tanks(id)
      ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
    ALTER TABLE public.tank_pairs VALIDATE CONSTRAINT fk_tank_pairs_mother;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_tank_pairs_father') THEN
    ALTER TABLE public.tank_pairs
      ADD CONSTRAINT fk_tank_pairs_father
      FOREIGN KEY (father_tank_id) REFERENCES public.tanks(id)
      ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
    ALTER TABLE public.tank_pairs VALIDATE CONSTRAINT fk_tank_pairs_father;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_crosses_tank_pair') THEN
    ALTER TABLE public.crosses
      ADD CONSTRAINT fk_crosses_tank_pair
      FOREIGN KEY (tank_pair_id) REFERENCES public.tank_pairs(id)
      ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
    ALTER TABLE public.crosses VALIDATE CONSTRAINT fk_crosses_tank_pair;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_ci_cross') THEN
    ALTER TABLE public.clutch_instances
      ADD CONSTRAINT fk_ci_cross
      FOREIGN KEY (cross_instance_id) REFERENCES public.crosses(id)
      ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
    ALTER TABLE public.clutch_instances VALIDATE CONSTRAINT fk_ci_cross;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_tc_ci') THEN
    ALTER TABLE public.treated_clutches
      ADD CONSTRAINT fk_tc_ci
      FOREIGN KEY (clutch_instance_id) REFERENCES public.clutch_instances(id)
      ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
    ALTER TABLE public.treated_clutches VALIDATE CONSTRAINT fk_tc_ci;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_tc_fish') THEN
    ALTER TABLE public.treated_clutches
      ADD CONSTRAINT fk_tc_fish
      FOREIGN KEY (fish_id) REFERENCES public.fish(id)
      ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
    ALTER TABLE public.treated_clutches VALIDATE CONSTRAINT fk_tc_fish;
  END IF;
END$$;

-- ===== Treatments / plates / slots =====
DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jct_tc') THEN
    ALTER TABLE public.join_clutch_treatments
      ADD CONSTRAINT fk_jct_tc
      FOREIGN KEY (treated_clutch_id) REFERENCES public.treated_clutches(id)
      ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
    ALTER TABLE public.join_clutch_treatments VALIDATE CONSTRAINT fk_jct_tc;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jct_treatment') THEN
    ALTER TABLE public.join_clutch_treatments
      ADD CONSTRAINT fk_jct_treatment
      FOREIGN KEY (treatment_id) REFERENCES public.treatments(id)
      ON UPDATE CASCADE ON DELETE RESTRICT NOT VALID;
    ALTER TABLE public.join_clutch_treatments VALIDATE CONSTRAINT fk_jct_treatment;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_plate_slots_plate') THEN
    ALTER TABLE public.plate_slots
      ADD CONSTRAINT fk_plate_slots_plate
      FOREIGN KEY (plate_id) REFERENCES public.plates(id)
      ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
    ALTER TABLE public.plate_slots VALIDATE CONSTRAINT fk_plate_slots_plate;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_plate_slots_tc') THEN
    ALTER TABLE public.plate_slots
      ADD CONSTRAINT fk_plate_slots_tc
      FOREIGN KEY (treated_clutch_id) REFERENCES public.treated_clutches(id)
      ON UPDATE CASCADE ON DELETE SET NULL NOT VALID;
    ALTER TABLE public.plate_slots VALIDATE CONSTRAINT fk_plate_slots_tc;
  END IF;
END$$;

-- ===== Fusions / payload =====
DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_fusions_fluor') THEN
    ALTER TABLE public.fusions
      ADD CONSTRAINT fk_fusions_fluor
      FOREIGN KEY (fluor_id) REFERENCES public.fluors(id)
      ON UPDATE CASCADE ON DELETE SET NULL NOT VALID;
    ALTER TABLE public.fusions VALIDATE CONSTRAINT fk_fusions_fluor;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_fusions_tag') THEN
    ALTER TABLE public.fusions
      ADD CONSTRAINT fk_fusions_tag
      FOREIGN KEY (tag_id) REFERENCES public.tags(id)
      ON UPDATE CASCADE ON DELETE SET NULL NOT VALID;
    ALTER TABLE public.fusions VALIDATE CONSTRAINT fk_fusions_tag;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jpf_plasmid') THEN
    ALTER TABLE public.join_plasmid_fusions
      ADD CONSTRAINT fk_jpf_plasmid
      FOREIGN KEY (plasmid_id) REFERENCES public.plasmids(id)
      ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
    ALTER TABLE public.join_plasmid_fusions VALIDATE CONSTRAINT fk_jpf_plasmid;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jpf_fusion') THEN
    ALTER TABLE public.join_plasmid_fusions
      ADD CONSTRAINT fk_jpf_fusion
      FOREIGN KEY (fusion_id) REFERENCES public.fusions(id)
      ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
    ALTER TABLE public.join_plasmid_fusions VALIDATE CONSTRAINT fk_jpf_fusion;
  END IF;
END$$;

-- ===== CRISPR (if present) =====
DO $$BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='crispr_knockins') THEN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jcf_knockin') THEN
      ALTER TABLE public.join_crispr_fusions
        ADD CONSTRAINT fk_jcf_knockin
        FOREIGN KEY (knockin_id) REFERENCES public.crispr_knockins(id)
        ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
      ALTER TABLE public.join_crispr_fusions VALIDATE CONSTRAINT fk_jcf_knockin;
    END IF;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='join_crispr_fusions') THEN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jcf_fusion') THEN
      ALTER TABLE public.join_crispr_fusions
        ADD CONSTRAINT fk_jcf_fusion
        FOREIGN KEY (fusion_id) REFERENCES public.fusions(id)
        ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
      ALTER TABLE public.join_crispr_fusions VALIDATE CONSTRAINT fk_jcf_fusion;
    END IF;
  END IF;
END$$;

-- ===== RNAs (if present) =====
DO $$BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='rnas') THEN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jrf_rna') THEN
      ALTER TABLE public.join_rna_fusions
        ADD CONSTRAINT fk_jrf_rna
        FOREIGN KEY (rna_id) REFERENCES public.rnas(id)
        ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
      ALTER TABLE public.join_rna_fusions VALIDATE CONSTRAINT fk_jrf_rna;
    END IF;
  END IF;
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='join_rna_fusions') THEN
    IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jrf_fusion') THEN
      ALTER TABLE public.join_rna_fusions
        ADD CONSTRAINT fk_jrf_fusion
        FOREIGN KEY (fusion_id) REFERENCES public.fusions(id)
        ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
      ALTER TABLE public.join_rna_fusions VALIDATE CONSTRAINT fk_jrf_fusion;
    END IF;
  END IF;
END$$;

-- ===== Fish / Transgenes =====
DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_class WHERE relname='uq_transgene_alleles_base_no') THEN
    CREATE UNIQUE INDEX uq_transgene_alleles_base_no
      ON public.transgene_alleles (transgene_base_code, allele_number);
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jfta_fish') THEN
    ALTER TABLE public.join_fish_transgene_alleles
      ADD CONSTRAINT fk_jfta_fish
      FOREIGN KEY (fish_id) REFERENCES public.fish(id)
      ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
    ALTER TABLE public.join_fish_transgene_alleles VALIDATE CONSTRAINT fk_jfta_fish;
  END IF;
END$$;

DO $$BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname='fk_jfta_allele') THEN
    ALTER TABLE public.join_fish_transgene_alleles
      ADD CONSTRAINT fk_jfta_allele
      FOREIGN KEY (transgene_base_code, allele_number)
      REFERENCES public.transgene_alleles(transgene_base_code, allele_number)
      ON UPDATE CASCADE ON DELETE CASCADE NOT VALID;
    ALTER TABLE public.join_fish_transgene_alleles VALIDATE CONSTRAINT fk_jfta_allele;
  END IF;
END$$;

COMMIT;
