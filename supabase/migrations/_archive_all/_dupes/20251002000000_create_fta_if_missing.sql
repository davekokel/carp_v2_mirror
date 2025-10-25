DO $$
BEGIN
  -- Create the table (no FK) if it doesn't exist
  IF to_regclass('public.fish_transgene_alleles') IS NULL THEN
    EXECUTE $T$
      CREATE TABLE public.fish_transgene_alleles (
        fish_id uuid NOT NULL,
        transgene_base_code text NOT NULL,
        allele_number integer NOT NULL,
        zygosity text,
        created_at timestamptz NOT NULL DEFAULT now(),
        created_by text,
        PRIMARY KEY (fish_id, transgene_base_code, allele_number)
      );
    $T$;
  END IF;

  -- If public.fish now exists, add the FK once (idempotent)
  IF to_regclass('public.fish') IS NOT NULL AND
     NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conname = 'fta_fish_fk') THEN
    EXECUTE $F$
      ALTER TABLE public.fish_transgene_alleles
      ADD CONSTRAINT fta_fish_fk
      FOREIGN KEY (fish_id) REFERENCES public.fish(id_uuid) ON DELETE CASCADE;
    $F$;
  END IF;
END
$$;
