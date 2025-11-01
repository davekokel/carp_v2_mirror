DO $$
BEGIN
  IF to_regclass('public.rna_registry') IS NOT NULL THEN
    EXECUTE 'DROP TABLE public.rna_registry CASCADE';
  END IF;
  IF to_regclass('public.rnas') IS NOT NULL THEN
    EXECUTE 'DROP TABLE public.rnas CASCADE';
  END IF;
  IF to_regclass('trash_carp.rna_registry') IS NOT NULL THEN
    EXECUTE 'DROP TABLE trash_carp.rna_registry CASCADE';
  END IF;
  IF to_regclass('trash_carp.rnas') IS NOT NULL THEN
    EXECUTE 'DROP TABLE trash_carp.rnas CASCADE';
  END IF;
END $$;
