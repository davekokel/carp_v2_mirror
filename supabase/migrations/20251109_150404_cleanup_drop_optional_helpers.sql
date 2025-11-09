BEGIN;

-- Drop old/optional helpers if present (we no longer call them from UI)
DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='ensure_ft_markers_from_transgene' AND pg_function_is_visible(oid)) THEN
    EXECUTE 'DROP FUNCTION public.ensure_ft_markers_from_transgene(text)';
  END IF;
END $$;

DO $$ BEGIN
  IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='upsert_transgene_allele' AND pg_function_is_visible(oid)) THEN
    EXECUTE 'DROP FUNCTION public.upsert_transgene_allele(text,text)';
  END IF;
END $$;

-- (Optional) any legacy resolvers you don't want lingering:
-- DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='resolve_fluor_id' AND pg_function_is_visible(oid)) THEN
--   EXECUTE 'DROP FUNCTION public.resolve_fluor_id(text)';
-- END IF; END $$;
-- DO $$ BEGIN IF EXISTS (SELECT 1 FROM pg_proc WHERE proname='resolve_tag_id' AND pg_function_is_visible(oid)) THEN
--   EXECUTE 'DROP FUNCTION public.resolve_tag_id(text)';
-- END IF; END $$;

COMMIT;
