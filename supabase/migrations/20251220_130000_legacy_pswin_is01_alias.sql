BEGIN;

UPDATE public.transgene_alleles
SET nickname = 'is01'
WHERE lower(transgene_base_code) = 'pswin-1'
  AND allele_number = 1;

DO $$
DECLARE n int;
BEGIN
  SELECT count(*) INTO n
  FROM public.transgene_alleles
  WHERE lower(transgene_base_code)='pswin-1'
    AND allele_number=1
    AND nickname='is01';

  IF n <> 1 THEN
    RAISE EXCEPTION 'Expected exactly 1 pswin-1 allele_number=1 row to have nickname=is01; got %', n;
  END IF;
END$$;

COMMIT;
