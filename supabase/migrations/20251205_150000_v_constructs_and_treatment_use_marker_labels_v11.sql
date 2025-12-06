BEGIN;

-- ─────────────────────────────────────────────────────
-- v_constructs_overview — use fluors/tags nickname/display_name/code
-- instead of fluor_code/tag_code
-- ─────────────────────────────────────────────────────
CREATE OR REPLACE VIEW public.v_constructs_overview AS
WITH base AS (
    SELECT
        c.id,
        c.construct_code,
        c.construct_kind,
        c.construct_name,
        c.resistance,
        COALESCE(c.plasmid_notes, c.description, ''::text) AS description,
        c.injection_use_plasmid,
        c.injection_use_rna,
        c.injection_use_crispr,
        c.created_at
    FROM public.constructs c
),
fusion_join AS (
    SELECT
        cf.construct_id,
        COUNT(DISTINCT cf.fusion_id) AS n_fusions,

        -- fusion_pretty: fluor-label + optional -tag-label + (pos)
        COALESCE(
            string_agg(
                DISTINCT
                    CASE
                        WHEN fl.id IS NULL THEN NULL::text
                        ELSE
                            COALESCE(fl.nickname, fl.display_name, fl.code) ||
                            COALESCE('-'::text || COALESCE(t.nickname, t.display_name, t.code), ''::text) ||
                            '('::text || COALESCE(f.tag_pos, ''::text) || ')'
                    END,
                '||'::text
            ),
            ''::text
        ) AS fusion_pretty,

        -- organelle_fluors: localization-fluor-label
        COALESCE(
            string_agg(
                DISTINCT
                    CASE
                        WHEN fl.id IS NULL THEN NULL::text
                        ELSE
                            COALESCE(t.localization, ''::text) ||
                            CASE
                                WHEN COALESCE(t.localization, ''::text) = ''::text THEN ''::text
                                ELSE '-'::text
                            END ||
                            COALESCE(fl.nickname, fl.display_name, fl.code)
                    END,
                '||'::text
            ),
            ''::text
        ) AS organelle_fluors
    FROM public.construct_fusions cf
    JOIN public.fusions f
      ON f.id = cf.fusion_id
    LEFT JOIN public.fluors fl
      ON fl.id = f.fluor_id
    LEFT JOIN public.tags t
      ON t.id = f.tag_id
    GROUP BY cf.construct_id
)
SELECT
    b.construct_code,
    b.construct_kind,
    b.construct_name,
    b.resistance,
    b.description,
    COALESCE(fj.n_fusions, 0::bigint) AS n_fusions,
    COALESCE(fj.fusion_pretty, ''::text) AS fusion_pretty,
    COALESCE(fj.organelle_fluors, ''::text) AS organelle_fluors,
    b.injection_use_plasmid,
    b.injection_use_rna,
    b.injection_use_crispr,
    b.created_at
FROM base b
LEFT JOIN fusion_join fj
  ON fj.construct_id = b.id;

-- ─────────────────────────────────────────────────────
-- v11_treatment_star — same marker label change
-- ─────────────────────────────────────────────────────
CREATE OR REPLACE VIEW public.v11_treatment_star AS
WITH mix_constructs AS (
    SELECT
        tm.treatment_id,
        tmc.construct_id
    FROM public.treatment_mixes tm
    JOIN public.treatment_mix_constructs tmc
      ON tmc.mix_id = tm.id
),
base_codes AS (
    SELECT
        mc.treatment_id,
        string_agg(
            DISTINCT c.construct_code,
            '; '::text
            ORDER BY c.construct_code
        ) AS genotype_basecode_code
    FROM mix_constructs mc
    JOIN public.constructs c
      ON c.id = mc.construct_id
    GROUP BY mc.treatment_id
),
constructs_by_kind AS (
    SELECT
        mc.treatment_id,
        c.construct_kind,
        string_agg(
            DISTINCT c.construct_code,
            ', '::text
            ORDER BY c.construct_code
        ) AS kind_codes
    FROM mix_constructs mc
    JOIN public.constructs c
      ON c.id = mc.construct_id
    GROUP BY mc.treatment_id, c.construct_kind
),
materials_by_kind AS (
    SELECT
        cbk.treatment_id,
        string_agg(
            format('%s(%s)', cbk.construct_kind, cbk.kind_codes),
            '; '::text
            ORDER BY cbk.construct_kind
        ) AS materials_by_kind
    FROM constructs_by_kind cbk
    GROUP BY cbk.treatment_id
),
fusion_bits AS (
    SELECT
        mc.treatment_id,
        COALESCE(fl.nickname, fl.display_name, fl.code) AS fluor_label,
        COALESCE(tg.nickname, tg.display_name, tg.code) AS tag_label,
        tg.localization,
        f.tag_pos,
        CASE
            WHEN tg.id IS NULL THEN
                format('%s::cytosol', COALESCE(fl.nickname, fl.display_name, fl.code))
            ELSE
                format(
                    '%s::%s(%s)',
                    COALESCE(fl.nickname, fl.display_name, fl.code),
                    COALESCE(tg.nickname, tg.display_name, tg.code),
                    f.tag_pos
                )
        END AS fluor_tag_label,
        format(
            '%s-%s',
            COALESCE(NULLIF(tg.localization, ''::text), 'cytosol'::text),
            COALESCE(fl.nickname, fl.display_name, fl.code)
        ) AS organelle_fluor_label
    FROM mix_constructs mc
    JOIN public.construct_fusions cf
      ON cf.construct_id = mc.construct_id
    JOIN public.fusions f
      ON f.id = cf.fusion_id
    JOIN public.fluors fl
      ON fl.id = f.fluor_id
    LEFT JOIN public.tags tg
      ON tg.id = f.tag_id
),
fluor_tag_rollup AS (
    SELECT
        s.treatment_id,
        string_agg(
            s.fluor_tag_label,
            '; '::text
            ORDER BY s.fluor_tag_label
        ) AS all_fluor_tag_rollup
    FROM (
        SELECT DISTINCT
            fb.treatment_id,
            fb.fluor_tag_label
        FROM fusion_bits fb
    ) s
    GROUP BY s.treatment_id
),
organelle_fluor_rollup AS (
    SELECT
        s.treatment_id,
        string_agg(
            s.organelle_fluor_label,
            '; '::text
            ORDER BY s.organelle_fluor_label
        ) AS all_organelle_fluor_rollup
    FROM (
        SELECT DISTINCT
            fb.treatment_id,
            fb.organelle_fluor_label
        FROM fusion_bits fb
    ) s
    GROUP BY s.treatment_id
)
SELECT
    t.id::text AS treatment_id,
    t.treat_code AS treatment_code,
    COALESCE(bc.genotype_basecode_code, ''::text) AS genotype_basecode_code,
    COALESCE(mk.materials_by_kind, ''::text) AS materials_by_kind,
    COALESCE(ft.all_fluor_tag_rollup, ''::text) AS all_fluor_tag_rollup,
    COALESCE(ofr.all_organelle_fluor_rollup, ''::text) AS all_organelle_fluor_rollup,
    t.kind_code,
    t.treat_text,
    t.created_at
FROM public.treatments t
LEFT JOIN base_codes bc
  ON bc.treatment_id = t.id
LEFT JOIN materials_by_kind mk
  ON mk.treatment_id = t.id
LEFT JOIN fluor_tag_rollup ft
  ON ft.treatment_id = t.id
LEFT JOIN organelle_fluor_rollup ofr
  ON ofr.treatment_id = t.id;

COMMIT;
