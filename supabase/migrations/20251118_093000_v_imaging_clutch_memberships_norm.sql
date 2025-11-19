BEGIN;

CREATE OR REPLACE VIEW public.v_imaging_clutch_memberships_norm AS
WITH ranked AS (
    SELECT
        m.*,
        ROW_NUMBER() OVER (
            PARTITION BY m.date_mount
            ORDER BY
                m.mount_id NULLS LAST,
                m.data_location
        ) AS slot_idx_raw
    FROM public.imaging_clutch_memberships m
)
SELECT
    r.id,
    r.clutch_id,
    r.sheet_row_index,
    r.date_born,
    r.zf_female_genotype_text,
    r.zf_male_genotype_text,
    r.date_mount,
    r.mount_id,
    r.data_location,
    r.row_plasmids_text,
    r.row_rnas_text,
    r.row_proteins_text,
    r.row_dyes_text,
    r.created_at,

    -- 1-based index of "slot" within the entire day
    r.slot_idx_raw                                        AS slot_index_global,

    -- 1×6 Bruker layout: 6 slots per plate
    ((r.slot_idx_raw - 1) / 6 + 1)                        AS plate_index,
    ((r.slot_idx_raw - 1) % 6 + 1)                        AS slot_index,

    -- Normalized IDs
    CASE
      WHEN r.date_mount IS NULL THEN NULL
      ELSE to_char(r.date_mount, 'YYYYMMDD')
           || '-plate' || ((r.slot_idx_raw - 1) / 6 + 1)
    END                                                   AS experimental_plate_id,

    CASE
      WHEN r.date_mount IS NULL THEN NULL
      ELSE to_char(r.date_mount, 'YYYYMMDD')
           || '-plate' || ((r.slot_idx_raw - 1) / 6 + 1)
           || '-slot'  || ((r.slot_idx_raw - 1) % 6 + 1)
    END                                                   AS experimental_slot_id

FROM ranked r;

COMMIT;
