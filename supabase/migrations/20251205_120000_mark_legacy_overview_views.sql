BEGIN;

ALTER VIEW IF EXISTS public.v_transgenes_overview
RENAME TO v_transgenes_overview_legacy;

ALTER VIEW IF EXISTS public.v_fusions_overview
RENAME TO v_fusions_overview_legacy;

ALTER VIEW IF EXISTS public.v_transgene_alleles_overview
RENAME TO v_transgene_alleles_overview_legacy;

ALTER VIEW IF EXISTS public.v_dyes_overview
RENAME TO v_dyes_overview_legacy;

ALTER VIEW IF EXISTS public.v_imaging_plate_slot_overview
RENAME TO v_imaging_plate_slot_overview_legacy;

COMMIT;
