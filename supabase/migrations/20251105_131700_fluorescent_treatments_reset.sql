BEGIN;

-- Ensure ft_injection_mixes exists and is wired
DO $$
BEGIN
  IF to_regclass('public.ft_injection_mixes') IS NULL THEN
    EXECUTE $ct$
      CREATE TABLE public.ft_injection_mixes (
        ft_code   text PRIMARY KEY,
        created_at timestamptz NOT NULL DEFAULT now()
      )
    $ct$;
  END IF;
END$$;

-- Ensure elements / proteins / dyes exist under the new names; do not drop existing data
DO $$
BEGIN
  IF to_regclass('public.ft_injection_mix_elements') IS NULL THEN
    EXECUTE $ct$
      CREATE TABLE public.ft_injection_mix_elements (
        mix_code   text    NOT NULL,
        source_key text    NOT NULL,
        source_val text    NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
      )
    $ct$;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='ft_injection_mix_elements'
      AND indexname='uq_ft_injection_mix_elements_key'
  ) THEN
    CREATE UNIQUE INDEX uq_ft_injection_mix_elements_key
      ON public.ft_injection_mix_elements(mix_code, source_key);
  END IF;

  IF to_regclass('public.ft_proteins') IS NULL THEN
    EXECUTE $ct$
      CREATE TABLE public.ft_proteins (
        id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        ft_code    text NOT NULL,
        fluor_code text NOT NULL,
        tag_code   text,
        created_at timestamptz NOT NULL DEFAULT now()
      )
    $ct$;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='ft_proteins'
      AND indexname='uq_ft_proteins_marker'
  ) THEN
    CREATE UNIQUE INDEX uq_ft_proteins_marker
      ON public.ft_proteins(ft_code, COALESCE(tag_code,'∅'), fluor_code);
  END IF;

  IF to_regclass('public.ft_dyes') IS NULL THEN
    EXECUTE $ct$
      CREATE TABLE public.ft_dyes (
        id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
        ft_code    text NOT NULL,
        dye_code   text NOT NULL,
        created_at timestamptz NOT NULL DEFAULT now()
      )
    $ct$;
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_indexes
    WHERE schemaname='public' AND tablename='ft_dyes'
      AND indexname='uq_ft_dyes_marker'
  ) THEN
    CREATE UNIQUE INDEX uq_ft_dyes_marker
      ON public.ft_dyes(ft_code, dye_code);
  END IF;
END$$;

-- Wire FKs (idempotent)
ALTER TABLE public.ft_injection_mixes
  DROP CONSTRAINT IF EXISTS fk_ftmix_ft;
ALTER TABLE public.ft_injection_mixes
  ADD  CONSTRAINT fk_ftmix_ft
  FOREIGN KEY (ft_code) REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE;

ALTER TABLE public.ft_injection_mix_elements
  DROP CONSTRAINT IF EXISTS fk_ftmixel_mix;
ALTER TABLE public.ft_injection_mix_elements
  ADD  CONSTRAINT fk_ftmixel_mix
  FOREIGN KEY (mix_code) REFERENCES public.ft_injection_mixes(ft_code) ON DELETE CASCADE;

ALTER TABLE public.ft_proteins
  DROP CONSTRAINT IF EXISTS fk_ftproteins_ft;
ALTER TABLE public.ft_proteins
  ADD  CONSTRAINT fk_ftproteins_ft
  FOREIGN KEY (ft_code) REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE;

ALTER TABLE public.ft_dyes
  DROP CONSTRAINT IF EXISTS fk_ftdyes_ft;
ALTER TABLE public.ft_dyes
  ADD  CONSTRAINT fk_ftdyes_ft
  FOREIGN KEY (ft_code) REFERENCES public.fluorescent_treatments(ft_code) ON DELETE CASCADE;

COMMIT;
