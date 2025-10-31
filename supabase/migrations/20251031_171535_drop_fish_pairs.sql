DO $$
BEGIN
  IF to_regclass('public.fish_pairs') IS NOT NULL THEN
    EXECUTE 'DROP TABLE public.fish_pairs CASCADE';
  END IF;
  IF to_regclass('trash_carp.fish_pairs') IS NOT NULL THEN
    EXECUTE 'DROP TABLE trash_carp.fish_pairs CASCADE';
  END IF;
END $$;
