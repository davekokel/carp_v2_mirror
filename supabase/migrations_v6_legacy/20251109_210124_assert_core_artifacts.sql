BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname='upsert_fish_by_identity') THEN
    RAISE EXCEPTION 'missing function: public.upsert_fish_by_identity';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname='upsert_transgene_allele') THEN
    RAISE EXCEPTION 'missing function: public.upsert_transgene_allele';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_proc p JOIN pg_namespace n ON n.oid=p.pronamespace WHERE n.nspname='public' AND p.proname='uuid_base36_8') THEN
    RAISE EXCEPTION 'missing function: public.uuid_base36_8';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.triggers WHERE trigger_schema='public' AND trigger_name='trg_clutch_default_treated') THEN
    RAISE EXCEPTION 'missing trigger: trg_clutch_default_treated';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.sequences WHERE sequence_schema='public' AND sequence_name='transgene_allele_global') THEN
    RAISE EXCEPTION 'missing sequence: transgene_allele_global';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.sequences WHERE sequence_schema='public' AND sequence_name='treated_clutch_seq') THEN
    RAISE EXCEPTION 'missing sequence: treated_clutch_seq';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='pgcrypto') THEN
    RAISE EXCEPTION 'missing extension: pgcrypto';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM pg_extension WHERE extname='uuid-ossp') THEN
    RAISE EXCEPTION 'missing extension: uuid-ossp';
  END IF;
END$$;
COMMIT;
