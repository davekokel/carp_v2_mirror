BEGIN;

-- ==========================================
-- 1) Drop legacy helpers (guarded)
-- ==========================================
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

-- Keep canonical helpers:
--   public.ensure_fusion_id(text,text,text)
--   public.resolve_symbol_id(text,text)
--   public.upsert_fish_by_identity(...)

-- ==========================================
-- 2) Drop FT stack (if present)
-- ==========================================
DO $$ BEGIN
  IF to_regclass('public.join_fish_fluorescent_treatments') IS NOT NULL THEN
    EXECUTE 'DROP TABLE public.join_fish_fluorescent_treatments';
  END IF;
END $$;

DO $$ BEGIN
  IF to_regclass('public.ft_proteins') IS NOT NULL THEN
    EXECUTE 'DROP TABLE public.ft_proteins';
  END IF;
END $$;

DO $$ BEGIN
  IF to_regclass('public.ft_dyes') IS NOT NULL THEN
    EXECUTE 'DROP TABLE public.ft_dyes';
  END IF;
END $$;

DO $$ BEGIN
  IF to_regclass('public.treatments_fluorescent') IS NOT NULL THEN
    EXECUTE 'DROP TABLE public.treatments_fluorescent';
  END IF;
END $$;

-- ==========================================
-- 3) Drop legacy views (guarded)
-- ==========================================
-- Add any you know you won't use anymore:
DO $$ DECLARE v text; BEGIN
  FOREACH v IN ARRAY ARRAY[
    'public.v_plasmids',
    'public.v_plasmids_rich',
    'public.v_fish_main',
    'public.v_fluorescent_marker_rollup',
    'public.v_fluorescent_marker_rollup_by_base'
  ]
  LOOP
    IF to_regclass(v) IS NOT NULL THEN
      EXECUTE 'DROP VIEW '||v;
    END IF;
  END LOOP;
END $$;

-- ==========================================
-- 4) Documentation
-- ==========================================
COMMENT ON SCHEMA public IS
  'Canonical marker path = fluors, tags, fusions, join_plasmid_fusions, join_rna_fusions.
   Fish genotype path    = transgenes, transgene_alleles, join_fish_transgene_alleles.
   Canonical helpers     = ensure_fusion_id, resolve_symbol_id, upsert_fish_by_identity.
   FT stack & rollup views intentionally removed.';

COMMIT;
