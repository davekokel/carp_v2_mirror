BEGIN;

DO $$
BEGIN
  -- join_fish_transgene_alleles
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE contype='p' AND conrelid='public.join_fish_transgene_alleles'::regclass
  ) THEN
    ALTER TABLE public.join_fish_transgene_alleles
      ADD CONSTRAINT pk_jfta PRIMARY KEY (fish_id, transgene_base_code, allele_number);
  END IF;

  -- join_plasmid_fusions
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE contype='p' AND conrelid='public.join_plasmid_fusions'::regclass
  ) THEN
    ALTER TABLE public.join_plasmid_fusions
      ADD CONSTRAINT pk_jpf PRIMARY KEY (plasmid_id, fusion_id);
  END IF;

  -- join_fish_fluorescent_treatments
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE contype='p' AND conrelid='public.join_fish_fluorescent_treatments'::regclass
  ) THEN
    ALTER TABLE public.join_fish_fluorescent_treatments
      ADD CONSTRAINT pk_jfft PRIMARY KEY (fish_id, ft_code);
  END IF;

  -- join_dyes_fluorescent_treatments
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE contype='p' AND conrelid='public.join_dyes_fluorescent_treatments'::regclass
  ) THEN
    ALTER TABLE public.join_dyes_fluorescent_treatments
      ADD CONSTRAINT pk_jdft PRIMARY KEY (dye_code, ft_code);
  END IF;

  -- join_clutch_treatments
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE contype='p' AND conrelid='public.join_clutch_treatments'::regclass
  ) THEN
    ALTER TABLE public.join_clutch_treatments
      ADD CONSTRAINT pk_jct PRIMARY KEY (clutch_instance_id, treatment_type, treatment_code);
  END IF;
END $$;

COMMIT;
