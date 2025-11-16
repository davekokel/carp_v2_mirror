BEGIN;

CREATE OR REPLACE VIEW public.v_legacy_roi_parent_fish_summary AS
SELECT
  c.parent_role,
  c.dataset,
  c.experiment_name,
  c.fish_label,
  c.roi_name,
  c.raw_roi_id,
  c.parent_plasmid_base_code,
  c.parent_allele_nickname,
  COUNT(DISTINCT c.candidate_fish_code)                        AS n_candidate_fish,
  array_agg(DISTINCT c.candidate_fish_code ORDER BY c.candidate_fish_code)     AS candidate_fish_codes,
  array_agg(DISTINCT c.candidate_fish_nickname ORDER BY c.candidate_fish_nickname) AS candidate_fish_nicknames
FROM public.v_legacy_roi_parent_fish_candidates c
GROUP BY
  c.parent_role,
  c.dataset,
  c.experiment_name,
  c.fish_label,
  c.roi_name,
  c.raw_roi_id,
  c.parent_plasmid_base_code,
  c.parent_allele_nickname;

COMMIT;
