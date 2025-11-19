BEGIN;

CREATE TABLE IF NOT EXISTS public.imaging_clutch_memberships (
    id                         uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    clutch_id                  uuid NOT NULL REFERENCES public.clutches(id) ON DELETE CASCADE,
    sheet_row_index            integer,
    date_born                  date,
    zf_female_genotype_text    text,
    zf_male_genotype_text      text,
    date_mount                 date,
    mount_id                   text,
    data_location              text,
    row_plasmids_text          text,
    row_rnas_text              text,
    row_proteins_text          text,
    row_dyes_text              text,
    created_at                 timestamp with time zone DEFAULT now()
);

CREATE INDEX IF NOT EXISTS imaging_clutch_memberships_clutch_id_idx
    ON public.imaging_clutch_memberships (clutch_id);

CREATE INDEX IF NOT EXISTS imaging_clutch_memberships_data_location_idx
    ON public.imaging_clutch_memberships (data_location);

COMMIT;
