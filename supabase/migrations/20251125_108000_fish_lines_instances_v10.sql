BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name   = 'fish_lines'
  ) THEN
    CREATE TABLE public.fish_lines (
      id                  uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
      line_code           text UNIQUE NOT NULL,
      nickname            text NOT NULL,
      genetic_background  text,
      line_building_stage text,
      notes               text,
      created_at          timestamptz NOT NULL DEFAULT now()
    );
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name   = 'join_line_alleles'
  ) THEN
    CREATE TABLE public.join_line_alleles (
      line_id        uuid NOT NULL REFERENCES public.fish_lines(id) ON DELETE CASCADE,
      construct_id   uuid NOT NULL REFERENCES public.constructs(id) ON DELETE RESTRICT,
      allele_number  int  NOT NULL,
      zygosity       text,
      created_at     timestamptz NOT NULL DEFAULT now(),
      PRIMARY KEY (line_id, construct_id, allele_number)
    );
  END IF;
END $$;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.tables
    WHERE table_schema = 'public'
      AND table_name   = 'fish_instances_v10'
  ) THEN
    CREATE TABLE public.fish_instances_v10 (
      id          uuid PRIMARY KEY DEFAULT uuid_generate_v4(),
      fish_code   text UNIQUE NOT NULL,
      line_id     uuid NOT NULL REFERENCES public.fish_lines(id) ON DELETE RESTRICT,
      birthday    date,
      notes       text,
      created_at  timestamptz NOT NULL DEFAULT now()
    );
  END IF;
END $$;

COMMIT;
