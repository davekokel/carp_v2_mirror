BEGIN;

ALTER TABLE public.ft_protein_markers DROP CONSTRAINT IF EXISTS fk_ftpm_fluor;
ALTER TABLE public.ft_protein_markers DROP CONSTRAINT IF EXISTS fk_ftpm_tag;
ALTER TABLE public.ft_dye_markers    DROP CONSTRAINT IF EXISTS fk_ftdm_dye;

DO $$
DECLARE col text;
BEGIN
  IF to_regclass('public.fluors') IS NOT NULL THEN
    SELECT column_name INTO col
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fluors'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','fluor_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'fluor_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
    LIMIT 1;
    IF col IS NOT NULL THEN
      EXECUTE 'ALTER TABLE public.ft_protein_markers ADD CONSTRAINT fk_ftpm_fluor FOREIGN KEY (fluor_code) REFERENCES public.fluors('||quote_ident(col)||')';
    ELSE
      RAISE NOTICE 'No compatible text column found in public.fluors';
    END IF;
  ELSIF to_regclass('public.fluor_names') IS NOT NULL THEN
    SELECT column_name INTO col
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='fluor_names'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','fluor_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'fluor_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
    LIMIT 1;
    IF col IS NOT NULL THEN
      EXECUTE 'ALTER TABLE public.ft_protein_markers ADD CONSTRAINT fk_ftpm_fluor FOREIGN KEY (fluor_code) REFERENCES public.fluor_names('||quote_ident(col)||')';
    ELSE
      RAISE NOTICE 'No compatible text column found in public.fluor_names';
    END IF;
  ELSE
    RAISE NOTICE 'Neither public.fluors nor public.fluor_names exist';
  END IF;

  IF to_regclass('public.tags') IS NOT NULL THEN
    SELECT column_name INTO col
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tags'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','tag_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'tag_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
    LIMIT 1;
    IF col IS NOT NULL THEN
      EXECUTE 'ALTER TABLE public.ft_protein_markers ADD CONSTRAINT fk_ftpm_tag FOREIGN KEY (tag_code) REFERENCES public.tags('||quote_ident(col)||')';
    ELSE
      RAISE NOTICE 'No compatible text column found in public.tags';
    END IF;
  ELSIF to_regclass('public.tag_names') IS NOT NULL THEN
    SELECT column_name INTO col
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='tag_names'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','tag_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'tag_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
    LIMIT 1;
    IF col IS NOT NULL THEN
      EXECUTE 'ALTER TABLE public.ft_protein_markers ADD CONSTRAINT fk_ftpm_tag FOREIGN KEY (tag_code) REFERENCES public.tag_names('||quote_ident(col)||')';
    ELSE
      RAISE NOTICE 'No compatible text column found in public.tag_names';
    END IF;
  ELSE
    RAISE NOTICE 'Neither public.tags nor public.tag_names exist';
  END IF;

  IF to_regclass('public.dyes') IS NOT NULL THEN
    SELECT column_name INTO col
    FROM information_schema.columns
    WHERE table_schema='public' AND table_name='dyes'
      AND data_type IN ('text','character varying')
      AND column_name IN ('code','dye_code','name')
    ORDER BY CASE column_name WHEN 'code' THEN 1 WHEN 'dye_code' THEN 2 WHEN 'name' THEN 3 ELSE 9 END
    LIMIT 1;
    IF col IS NOT NULL THEN
      EXECUTE 'ALTER TABLE public.ft_dye_markers ADD CONSTRAINT fk_ftdm_dye FOREIGN KEY (dye_code) REFERENCES public.dyes('||quote_ident(col)||')';
    ELSE
      RAISE NOTICE 'No compatible text column found in public.dyes';
    END IF;
  ELSE
    RAISE NOTICE 'public.dyes does not exist';
  END IF;
END$$;

COMMIT;
