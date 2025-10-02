DROP VIEW IF EXISTS public.v_fish_overview;

CREATE VIEW public.v_fish_overview AS
SELECT
  f.id_uuid AS fish_id,
  f.fish_code,
  f.nickname,
  f.line_building_stage,
  f.created_by,
  f.date_of_birth,

  -- Transgene info
  fta.transgene_base_code,
  fta.allele_number,
  tg.name AS transgene_name,

  -- Injected plasmid info
  ipt.plasmid_id AS injected_plasmid_id,
  p1.name AS injected_plasmid_name,

  -- Injected RNA info
  irt.rna_id AS injected_rna_id,
  r.name AS injected_rna_name

FROM public.fish f

-- Transgene link
LEFT JOIN public.fish_transgene_alleles fta
  ON f.id_uuid = fta.fish_id
LEFT JOIN public.transgene_alleles ta
  ON fta.transgene_base_code = ta.transgene_base_code
  AND fta.allele_number = ta.allele_number
LEFT JOIN public.transgenes tg
  ON ta.transgene_base_code = tg.transgene_base_code

-- Injected plasmids
LEFT JOIN public.injected_plasmid_treatments ipt
  ON f.id_uuid = ipt.fish_id
LEFT JOIN public.plasmids p1
  ON ipt.plasmid_id = p1.id_uuid

-- Injected RNAs
LEFT JOIN public.injected_rna_treatments irt
  ON f.id_uuid = irt.fish_id
LEFT JOIN public.rnas r
  ON irt.rna_id = r.id_uuid;