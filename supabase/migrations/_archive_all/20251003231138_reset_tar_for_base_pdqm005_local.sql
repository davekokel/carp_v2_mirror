BEGIN;

DO $body$
DECLARE
  has_mod boolean;
  has_legacy boolean;
BEGIN
  -- detect column layout in transgene_allele_registry
  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='transgene_allele_registry' AND column_name='transgene_base_code'
  ) INTO has_mod;

  SELECT EXISTS (
    SELECT 1 FROM information_schema.columns
    WHERE table_schema='public' AND table_name='transgene_allele_registry' AND column_name='base_code'
  ) INTO has_legacy;

  IF to_regclass('public.transgene_allele_registry') IS NOT NULL THEN
    IF has_mod THEN
      EXECUTE $$DELETE FROM public.transgene_allele_registry WHERE transgene_base_code = 'pDQM005'$$;
    ELSIF has_legacy THEN
      EXECUTE $$DELETE FROM public.transgene_allele_registry WHERE base_code = 'pDQM005'$$;
    END IF;
  END IF;

  IF to_regclass('public.transgene_allele_counters') IS NOT NULL THEN
    EXECUTE $$DELETE FROM public.transgene_allele_counters WHERE transgene_base_code = 'pDQM005'$$;
  END IF;
END
$body$;

COMMIT;
