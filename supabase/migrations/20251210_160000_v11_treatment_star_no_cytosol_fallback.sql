BEGIN;

-- Rebuild v11_treatment_star to remove "cytosol" fallback.
-- If there is no tag, we no longer fabricate mStayGold::cytosol / cytosol-mStayGold.
-- Instead, we just use the fluor label alone.

CREATE OR REPLACE VIEW public.v11_treatment_star AS
WITH mix_constructs AS (
  SELECT tm.treatment_id, tmc.construct_id
  FROM public.treatment_mixes tm
  JOIN public.treatment_mix_constructs tmc ON tmc.mix_id = tm.id
),
base_codes AS (
  SELECT mc.treatment_id,
         string_agg(DISTINCT c.construct_code, '; ' ORDER BY c.construct_code)
           AS genotype_basecode_code
  FROM mix_constructs mc
  JOIN public.constructs c ON c.id = mc.construct_id
  GROUP BY mc.treatment_id
),
constructs_by_kind AS (
  SELECT mc.treatment_id,
         c.construct_kind,
         string_agg(DISTINCT c.construct_code, ', ' ORDER BY c.construct_code)
           AS kind_codes
  FROM mix_constructs mc
  JOIN public.constructs c ON c.id = mc.construct_id
  GROUP BY mc.treatment_id, c.construct_kind
),
materials_by_kind AS (
  SELECT cbk.treatment_id,
         string_agg(
           format('%s(%s)', cbk.construct_kind, cbk.kind_codes),
           '; ' ORDER BY cbk.construct_kind
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
    -- NEW: do NOT invent fluor::cytosol when no tag.
    CASE
      WHEN tg.id IS NULL
        THEN COALESCE(fl.nickname, fl.display_name, fl.code)
      ELSE format(
        '%s::%s(%s)',
        COALESCE(fl.nickname, fl.display_name, fl.code),
        COALESCE(tg.nickname, tg.display_name, tg.code),
        f.tag_pos
      )
    END AS fluor_tag_label,
    -- NEW: do NOT invent "cytosol-" prefix when localization is missing.
    CASE
      WHEN tg.localization IS NULL OR tg.localization = ''
        THEN COALESCE(fl.nickname, fl.display_name, fl.code)
      ELSE format(
        '%s-%s',
        tg.localization,
        COALESCE(fl.nickname, fl.display_name, fl.code)
      )
    END AS organelle_fluor_label
  FROM mix_constructs mc
  JOIN public.construct_fusions cf ON cf.construct_id = mc.construct_id
  JOIN public.fusions f           ON f.id = cf.fusion_id
  JOIN public.fluors fl           ON fl.id = f.fluor_id
  LEFT JOIN public.tags tg        ON tg.id = f.tag_id
),
fluor_tag_rollup AS (
  SELECT s.treatment_id,
         string_agg(s.fluor_tag_label, '; ' ORDER BY s.fluor_tag_label)
           AS all_fluor_tag_rollup
  FROM (
    SELECT DISTINCT fb.treatment_id, fb.fluor_tag_label
    FROM fusion_bits fb
  ) s
  GROUP BY s.treatment_id
),
organelle_fluor_rollup AS (
  SELECT s.treatment_id,
         string_agg(s.organelle_fluor_label, '; ' ORDER BY s.organelle_fluor_label)
           AS all_organelle_fluor_rollup
  FROM (
    SELECT DISTINCT fb.treatment_id, fb.organelle_fluor_label
    FROM fusion_bits fb
  ) s
  GROUP BY s.treatment_id
)
SELECT
  t.id::text AS treatment_id,
  t.treat_code AS treatment_code,
  COALESCE(bc.genotype_basecode_code, '')        AS genotype_basecode_code,
  COALESCE(mk.materials_by_kind, '')             AS materials_by_kind,
  COALESCE(ft.all_fluor_tag_rollup, '')          AS all_fluor_tag_rollup,
  COALESCE(ofr.all_organelle_fluor_rollup, '')   AS all_organelle_fluor_rollup,
  t.kind_code,
  t.treat_text,
  t.created_at
FROM public.treatments t
LEFT JOIN base_codes            bc  ON bc.treatment_id = t.id
LEFT JOIN materials_by_kind     mk  ON mk.treatment_id = t.id
LEFT JOIN fluor_tag_rollup      ft  ON ft.treatment_id = t.id
LEFT JOIN organelle_fluor_rollup ofr ON ofr.treatment_id = t.id;

COMMIT;
