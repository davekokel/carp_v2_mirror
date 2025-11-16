BEGIN;

-- 1) Map each transgene allele nickname to all fish that carry it
CREATE OR REPLACE VIEW public.v_legacy_parent_allele_fish AS
SELECT
  ta.transgene_base_code,
  ta.allele_nickname,
  ta.allele_number,
  f.id        AS fish_id,
  f.fish_code AS fish_code,
  f.nickname  AS fish_nickname
FROM public.transgene_alleles ta
JOIN public.join_fish_transgene_alleles jfta
  ON jfta.transgene_base_code = ta.transgene_base_code
 AND jfta.allele_number       = ta.allele_number
JOIN public.fish f
  ON f.id = jfta.fish_id;


-- 2) For each ROI, list candidate mother/father fish based on normalized parent alleles
CREATE OR REPLACE VIEW public.v_legacy_roi_parent_fish_candidates AS
WITH base AS (
  SELECT
    r.raw_roi_id,
    r.dataset,
    r.experiment_name,
    r.fish_label,
    r.roi_name,
    r.mother_plasmid_base_code,
    r.mother_allele_nickname,
    r.father_plasmid_base_code,
    r.father_allele_nickname
  FROM public.v_legacy_roi_overview r
)
SELECT
  'mother'                 AS parent_role,
  b.dataset,
  b.experiment_name,
  b.fish_label,
  b.roi_name,
  b.raw_roi_id,
  b.mother_plasmid_base_code  AS parent_plasmid_base_code,
  b.mother_allele_nickname    AS parent_allele_nickname,
  paf.fish_code               AS candidate_fish_code,
  paf.fish_nickname           AS candidate_fish_nickname
FROM base b
JOIN public.v_legacy_parent_allele_fish paf
  ON paf.transgene_base_code = b.mother_plasmid_base_code
 AND paf.allele_nickname     = b.mother_allele_nickname

UNION ALL

SELECT
  'father'                 AS parent_role,
  b.dataset,
  b.experiment_name,
  b.fish_label,
  b.roi_name,
  b.raw_roi_id,
  b.father_plasmid_base_code  AS parent_plasmid_base_code,
  b.father_allele_nickname    AS parent_allele_nickname,
  paf.fish_code               AS candidate_fish_code,
  paf.fish_nickname           AS candidate_fish_nickname
FROM base b
JOIN public.v_legacy_parent_allele_fish paf
  ON paf.transgene_base_code = b.father_plasmid_base_code
 AND paf.allele_nickname     = b.father_allele_nickname;

COMMIT;
