BEGIN;

-- Views may depend on the marker tables; drop them safely first.
DROP VIEW IF EXISTS public.v_fish_fluorescent_markers;
DROP VIEW IF EXISTS public.v_fluorescent_treatment_markers;

-- v4 canonical marker tables (ft_proteins / ft_dyes)
DROP TABLE IF EXISTS public.ft_proteins CASCADE;
CREATE TABLE public.ft_proteins (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ft_code    text NOT NULL,
  fluor_code text NOT NULL,
  tag_code   text,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_proteins_marker
  ON public.ft_proteins(ft_code, COALESCE(tag_code,'∅'), fluor_code);

DROP TABLE IF EXISTS public.ft_dyes CASCADE;
CREATE TABLE public.ft_dyes (
  id         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  ft_code    text NOT NULL,
  dye_code   text NOT NULL,
  created_at timestamptz NOT NULL DEFAULT now()
);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_dyes_marker
  ON public.ft_dyes(ft_code, dye_code);

-- Required FK to the FT canon
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

-- Optional FKs to lookup tables when present (supports either modern fluors/tags/dyes or none)
DO $$
DECLARE col text;
BEGIN
  IF to_regclass('public.fluors') IS NOT NULL THEN
    SELECT column_name INTO col FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fluors'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','fluor_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'fluor_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END LIMIT 1;
    IF col IS NOT NULL THEN
      EXECUTE format('ALTER TABLE public.ft_proteins ADD CONSTRAINT fk_ftproteins_fluor FOREIGN KEY (fluor_code) REFERENCES public.fluors(%I)', col);
    END IF;
  END IF;

  IF to_regclass('public.tags') IS NOT NULL THEN
    SELECT column_name INTO col FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tags'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','tag_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'tag_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END LIMIT 1;
    IF col IS NOT NULL THEN
      EXECUTE format('ALTER TABLE public.ft_proteins ADD CONSTRAINT fk_ftproteins_tag FOREIGN KEY (tag_code) REFERENCES public.tags(%I)', col);
    END IF;
  END IF;

  IF to_regclass('public.dyes') IS NOT NULL THEN
    SELECT column_name INTO col FROM information_schema.columns
    WHERE table_schema='public' AND table_name='dyes'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','dye_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'dye_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END LIMIT 1;
    IF col IS NOT NULL THEN
      EXECUTE format('ALTER TABLE public.ft_dyes ADD CONSTRAINT fk_ftdyes_dye FOREIGN KEY (dye_code) REFERENCES public.dyes(%I)', col);
    END IF;
  END IF;
END$$;

COMMIT;
