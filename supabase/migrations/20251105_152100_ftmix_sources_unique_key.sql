BEGIN;
DO $$
DECLARE mix_col text;
BEGIN
  SELECT column_name INTO mix_col
  FROM information_schema.columns
  WHERE table_schema='public' AND table_name='ft_injection_mix_elements'
    AND column_name IN ('mix_code','ft_code','injection_mix_code')
  ORDER BY CASE column_name
             WHEN 'mix_code' THEN 1
             WHEN 'ft_code' THEN 2
             WHEN 'injection_mix_code' THEN 3
             ELSE 9
           END
  LIMIT 1;

  IF mix_col IS NULL THEN
    RAISE EXCEPTION 'ft_injection_mix_elements needs a mix key column (mix_code/ft_code/injection_mix_code)';
  END IF;

  EXECUTE format(
    'CREATE UNIQUE INDEX IF NOT EXISTS uq_ft_injection_mix_elements_key
       ON public.ft_injection_mix_elements(%I, source_key)',
    mix_col
  );
END$$;
COMMIT;
