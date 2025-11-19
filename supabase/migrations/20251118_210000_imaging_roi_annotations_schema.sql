BEGIN;

DROP VIEW IF EXISTS public.v_roi_overview;

DROP TABLE IF EXISTS public.imaging_roi_annotations;

CREATE TABLE public.imaging_roi_annotations (
    "roi_dir"                       text,
    "date_experiment"               text,
    "fish"                          text,
    "roi_name"                      text,
    "date_born"                     text,
    "parent_female"                 text,
    "parent_male"                   text,
    "genotype_base_codes"           text,
    "genotype_allele_codes"         text,
    "genotype_pretty"               text,
    "genotype_marker_fluor_codes"   text,
    "genotype_marker_tag_codes"     text,
    "treatment_plasmid_base_codes"  text,
    "treatment_rna_base_codes"      text,
    "treatment_marker_fluor_codes"  text,
    "treatment_marker_tag_codes"    text,
    "all_marker_fluor_codes"        text,
    "additional plasmids injected"  text,
    "additional mRNAs injected"     text,
    "additonal proteins injected"   text,
    "additonal dye and chemicals"   text,
    "Date born"                     text,
    "ZF female genotype"            text,
    "ZF male genotype"              text,
    "Data location"                 text,
    "plate_id_filled"               text,
    "slot_id_filled"                text,
    "roi_index_within_slot"         double precision,
    "roi_code"                      text
);

-- Temporary/simple v_roi_overview: pass-through of imaging_roi_annotations.
-- We can later refine this to join fish, clutches, etc.
CREATE OR REPLACE VIEW public.v_roi_overview AS
SELECT *
FROM public.imaging_roi_annotations;

COMMIT;
