BEGIN;

CREATE OR REPLACE VIEW public.v_legacy_roi_parent_fish_unique AS
SELECT
  parent_role,
  dataset,
  experiment_name,
  fish_label,
  roi_name,
  raw_roi_id,
  parent_plasmid_base_code,
  parent_allele_nickname,
  candidate_fish_codes[1]     AS fish_code,
  candidate_fish_nicknames[1] AS fish_nickname
FROM public.v_legacy_roi_parent_fish_summary
WHERE n_candidate_fish = 1;

COMMIT;
