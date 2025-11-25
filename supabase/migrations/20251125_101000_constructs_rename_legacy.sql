BEGIN;

-- Rename v8-era construct-related tables to *_legacy
DO $$
BEGIN
  IF to_regclass('public.plasmids') IS NOT NULL THEN
    ALTER TABLE public.plasmids RENAME TO plasmids_legacy;
  END IF;
  IF to_regclass('public.rnas') IS NOT NULL THEN
    ALTER TABLE public.rnas RENAME TO rnas_legacy;
  END IF;
  IF to_regclass('public.crisprs') IS NOT NULL THEN
    ALTER TABLE public.crisprs RENAME TO crisprs_legacy;
  END IF;
  IF to_regclass('public.join_plasmid_fusions') IS NOT NULL THEN
    ALTER TABLE public.join_plasmid_fusions RENAME TO join_plasmid_fusions_legacy;
  END IF;
  IF to_regclass('public.join_rna_fusions') IS NOT NULL THEN
    ALTER TABLE public.join_rna_fusions RENAME TO join_rna_fusions_legacy;
  END IF;
END $$;

COMMIT;
