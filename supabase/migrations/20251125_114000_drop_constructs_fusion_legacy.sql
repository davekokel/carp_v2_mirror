BEGIN;

-- Drop legacy plasmid/fusion snapshots that are no longer used in v10

DROP TABLE IF EXISTS public.join_plasmid_fusions_legacy CASCADE;
DROP TABLE IF EXISTS public.join_rna_fusions_legacy CASCADE;
DROP TABLE IF EXISTS public.plasmids_legacy CASCADE;

-- If you have any legacy views built on these, drop them too.
DROP VIEW IF EXISTS public.v_plasmids_overview_legacy CASCADE;

COMMIT;
