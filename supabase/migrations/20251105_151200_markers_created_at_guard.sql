BEGIN;

ALTER TABLE public.ft_protein_markers ADD COLUMN IF NOT EXISTS created_at timestamptz;
ALTER TABLE public.ft_dye_markers     ADD COLUMN IF NOT EXISTS created_at timestamptz;

UPDATE public.ft_protein_markers SET created_at = now() WHERE created_at IS NULL;
UPDATE public.ft_dye_markers     SET created_at = now() WHERE created_at IS NULL;

ALTER TABLE public.ft_protein_markers ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE public.ft_protein_markers ALTER COLUMN created_at SET NOT NULL;
ALTER TABLE public.ft_dye_markers     ALTER COLUMN created_at SET DEFAULT now();
ALTER TABLE public.ft_dye_markers     ALTER COLUMN created_at SET NOT NULL;

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='ft_protein_markers'
      AND column_name='created_at' AND is_nullable='NO'
  ) THEN
    RAISE EXCEPTION 'ft_protein_markers.created_at must be NOT NULL with DEFAULT now()';
  END IF;

  IF NOT EXISTS (
    SELECT 1
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='ft_dye_markers'
      AND column_name='created_at' AND is_nullable='NO'
  ) THEN
    RAISE EXCEPTION 'ft_dye_markers.created_at must be NOT NULL with DEFAULT now()';
  END IF;
END$$;

COMMIT;
