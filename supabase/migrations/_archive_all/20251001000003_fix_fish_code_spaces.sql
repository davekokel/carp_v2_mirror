DO $$
BEGIN
  IF to_regclass('public.fish') IS NOT NULL THEN
    EXECUTE $U$
      UPDATE public.fish
      SET fish_code = replace(fish_code, ' ', '')
      WHERE fish_code LIKE '% %'
    $U$;
  END IF;
END
$$;
