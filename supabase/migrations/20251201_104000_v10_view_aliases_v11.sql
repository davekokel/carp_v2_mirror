BEGIN;

-- v10 fish groups overview
DROP VIEW IF EXISTS public.v10_fish_groups_overview;
CREATE VIEW public.v10_fish_groups_overview AS
SELECT *
FROM public.v_fish_groups_overview;

-- v10 tanks overview
DROP VIEW IF EXISTS public.v10_tanks_overview;
CREATE VIEW public.v10_tanks_overview AS
SELECT *
FROM public.v_tanks_overview;

-- v10 imaging ROI overview
DROP VIEW IF EXISTS public.v10_imaging_roi_overview;
CREATE VIEW public.v10_imaging_roi_overview AS
SELECT *
FROM public.v_roi_overview;

-- v10 imaging clutches → ROIs
DROP VIEW IF EXISTS public.v10_imaging_clutches_rois;
CREATE VIEW public.v10_imaging_clutches_rois AS
SELECT *
FROM public.v_imaging_clutches_rois;

-- v10 fusions overview
DROP VIEW IF EXISTS public.v10_fusions_overview;
CREATE VIEW public.v10_fusions_overview AS
SELECT *
FROM public.v_fusions_overview;

-- v10 dyes overview
DROP VIEW IF EXISTS public.v10_dyes_overview;
CREATE VIEW public.v10_dyes_overview AS
SELECT *
FROM public.v_dyes_overview;

-- v10 transgenes overview
DROP VIEW IF EXISTS public.v10_transgenes_overview;
CREATE VIEW public.v10_transgenes_overview AS
SELECT *
FROM public.v_transgenes_overview;

-- v10 transgene alleles overview
DROP VIEW IF EXISTS public.v10_transgene_alleles_overview;
CREATE VIEW public.v10_transgene_alleles_overview AS
SELECT *
FROM public.v_transgene_alleles_overview;

COMMIT;
