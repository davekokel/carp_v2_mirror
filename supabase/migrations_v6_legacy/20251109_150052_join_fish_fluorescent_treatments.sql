BEGIN;

-- Create treatments_fluorescent stub if truly missing (safe if exists)
CREATE TABLE IF NOT EXISTS public.treatments_fluorescent (
  id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ft_code text UNIQUE NOT NULL,
  ft_text text,
  created_by text,
  created_at timestamptz NOT NULL DEFAULT now()
);

-- Create the join table
CREATE TABLE IF NOT EXISTS public.join_fish_fluorescent_treatments (
  fish_id uuid NOT NULL,
  ft_code text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now(),
  PRIMARY KEY (fish_id, ft_code),
  CONSTRAINT fk_jff_fish FOREIGN KEY (fish_id) REFERENCES public.fish(id) ON DELETE CASCADE
);

-- Optional FK to treatments_fluorescent.ft_code if that table/column exist (guarded)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='treatments_fluorescent' AND column_name='ft_code'
  ) THEN
    IF NOT EXISTS (
      SELECT 1 FROM information_schema.table_constraints
      WHERE table_schema='public' AND table_name='join_fish_fluorescent_treatments' AND constraint_name='fk_jff_ftcode'
    ) THEN
      ALTER TABLE public.join_fish_fluorescent_treatments
      ADD CONSTRAINT fk_jff_ftcode
      FOREIGN KEY (ft_code) REFERENCES public.treatments_fluorescent(ft_code)
      ON UPDATE CASCADE ON DELETE RESTRICT;
    END IF;
  END IF;
END$$;

COMMIT;
