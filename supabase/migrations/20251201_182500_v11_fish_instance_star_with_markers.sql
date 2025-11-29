BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_instance_star AS
WITH fi_base AS (
    SELECT
        fi.id                     AS fish_instance_id,
        fi.fish_code,
        fi.line_id,
        fi.line_instance_code,
        fi.birthday,
        fi.notes                  AS fish_notes,
        fi.created_at             AS fish_created_at,

        fl.line_code,
        fl.nickname               AS line_nickname,
        fl.genetic_background,
        fl.line_building_stage,
        fl.created_at             AS line_created_at,

        fl.fish_group_id,
        fg.group_code,
        fl.group_instance_code,

        -- genotype from v11_line_allele_rollups (canonical)
        la.allele_label_rollup    AS genotype_pretty,
        la.allele_canonical_rollup AS genotype_basecode_code,
        la.allele_label_rollup    AS genotype_transgene_allele_code,

        -- tank
        t.id                      AS tank_id,
        t.tank_code,
        t.status                  AS tank_status,
        t.created_at              AS tank_created_at

    FROM public.fish_instances_v10 fi
    JOIN public.fish_lines fl
      ON fl.id = fi.line_id
    LEFT JOIN public.fish_groups fg
      ON fg.id = fl.fish_group_id
    LEFT JOIN public.v11_line_allele_rollups la
      ON la.line_id = fl.id
    LEFT JOIN public.tanks t
      ON t.fish_instance_id = fi.id
),
markers AS (
    SELECT
        lf.line_id,
        COALESCE(lf.fluor_codes, '') AS fluor_codes,
        COALESCE(lf.tag_codes,   '') AS tag_codes
    FROM public.v10_line_fluors lf
)
SELECT
    b.fish_instance_id,
    b.fish_code,
    b.line_id,
    b.line_instance_code,
    b.birthday,
    b.fish_notes,
    b.fish_created_at,
    b.line_code,
    b.line_nickname,
    b.genetic_background,
    b.line_building_stage,
    b.line_created_at,
    b.fish_group_id,
    b.group_code,
    b.group_instance_code,

    -- genotype fields (same names as before)
    b.genotype_pretty,

    -- marker fields now sourced from v10_line_fluors
    m.fluor_codes,
    m.tag_codes,
    NULL::text AS organelle_fluors,

    -- tank
    b.tank_id,
    b.tank_code,
    b.tank_status,
    b.tank_created_at,

    -- per-fish treatment code (still empty in current v11)
    NULL::text AS treatment_code,

    -- existing genotype rollups
    b.genotype_basecode_code,
    b.genotype_transgene_allele_code,

    -- semantic rollups
    CASE
        WHEN b.genotype_basecode_code IS NULL AND (m.fluor_codes IS NULL OR m.fluor_codes = '')
            THEN NULL
        WHEN b.genotype_basecode_code IS NULL
            THEN m.fluor_codes
        WHEN m.fluor_codes IS NULL OR m.fluor_codes = ''
            THEN b.genotype_basecode_code
        ELSE b.genotype_basecode_code || ' || ' || m.fluor_codes
    END AS treatments_and_transgenes,

    m.fluor_codes AS all_fluor_tag_rollup,
    NULL::text    AS all_organelle_fluor_rollup

FROM fi_base b
LEFT JOIN markers m
  ON m.line_id = b.line_id
ORDER BY b.fish_code;

COMMIT;
