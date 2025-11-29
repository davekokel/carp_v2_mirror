BEGIN;

CREATE OR REPLACE VIEW public.v11_fish_instance_star AS
WITH fi_base AS (
    SELECT
        fi.id                  AS fish_instance_id,
        fi.fish_code           AS fish_code,
        fi.line_id             AS line_id,
        fi.line_instance_code  AS line_instance_code,
        fi.birthday            AS birthday,
        fi.notes               AS fish_notes,
        fi.created_at          AS fish_created_at,

        fl.line_code           AS line_code,
        fl.nickname            AS line_nickname,
        fl.genetic_background  AS genetic_background,
        fl.line_building_stage AS line_building_stage,
        fl.created_at          AS line_created_at,
        fl.fish_group_id       AS fish_group_id,
        fl.group_instance_code AS group_instance_code,

        fg.group_code          AS group_code,

        -- v10 group overview gives us basecode genotype + marker rollups
        gf.basecode_genotype   AS genotype_basecode_code,
        gf.fluor_tag           AS group_fluor_tag,
        gf.organelle_fluor     AS organelle_fluors,
        gf.basecode_genotype   AS genotype_transgene_allele_code,

        t.id                   AS tank_id,
        t.tank_code            AS tank_code,
        t.status               AS tank_status,
        t.created_at           AS tank_created_at,

        fi.genotype_v11_id     AS genotype_v11_id
    FROM public.fish_instances_v10 fi
    JOIN public.fish_lines fl
      ON fl.id = fi.line_id
    LEFT JOIN public.fish_groups fg
      ON fg.id = fl.fish_group_id
    LEFT JOIN public.v10_fish_groups_overview gf
      ON gf.fish_group_id::uuid = fl.fish_group_id
    LEFT JOIN public.tanks t
      ON t.fish_instance_id = fi.id
),
markers AS (
    SELECT
        lf.line_id,
        lf.fluor_codes,
        lf.tag_codes
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

    -- we use the basecode genotype as the "pretty" label here
    b.genotype_basecode_code AS genotype_pretty,

    -- per-line markers from v10_line_fluors
    m.fluor_codes,
    m.tag_codes,
    b.organelle_fluors,

    -- tank info
    b.tank_id,
    b.tank_code,
    b.tank_status,
    b.tank_created_at,

    -- legacy / placeholder; we keep schema stable
    NULL::text AS treatment_code,

    -- explicit genotype fields
    b.genotype_basecode_code,
    b.genotype_transgene_allele_code,

    -- combined transgenes + markers (exactly as before)
    CASE
        WHEN b.genotype_basecode_code IS NULL OR b.genotype_basecode_code = '' THEN m.fluor_codes
        WHEN m.fluor_codes IS NULL OR m.fluor_codes = '' THEN b.genotype_basecode_code
        ELSE b.genotype_basecode_code || ' || ' || m.fluor_codes
    END AS treatments_and_transgenes,

    -- fluor::tag(tag_pos) rollup (we only know tags, not position, so we bake N)
    CASE
        WHEN m.fluor_codes IS NOT NULL AND m.fluor_codes <> '' THEN
            CASE
                WHEN m.tag_codes IS NOT NULL AND m.tag_codes <> '' THEN
                    m.fluor_codes || '::' || m.tag_codes || '(N)'
                ELSE
                    REPLACE(m.fluor_codes, ',', ' +')
            END
        ELSE
            NULL
    END AS all_fluor_tag_rollup,

    -- organelle rollup with cytosol default:
    -- 1) if we have explicit organelles from groups, use those
    -- 2) else if we have any fluor codes at all, default to 'cytosol'
    -- 3) otherwise NULL
    CASE
        WHEN b.organelle_fluors IS NOT NULL AND b.organelle_fluors <> '' THEN
            b.organelle_fluors
        WHEN m.fluor_codes IS NOT NULL AND m.fluor_codes <> '' THEN
            'cytosol'
        ELSE
            NULL
    END AS all_organelle_fluor_rollup

FROM fi_base b
LEFT JOIN markers m
  ON m.line_id = b.line_id
ORDER BY b.fish_code;

COMMIT;
