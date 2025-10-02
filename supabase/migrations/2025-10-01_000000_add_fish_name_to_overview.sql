-- Recreate view v_fish_overview with added fish_name column

drop view if exists public.v_fish_overview;

create view public.v_fish_overview as
select
  f.id_uuid as fish_id,
  f.fish_code,
  f.name as fish_name,
  f.nickname,
  f.line_building_stage,
  f.created_by,
  f.date_of_birth,
  fta.transgene_base_code,
  fta.allele_number,
  tg.name as transgene_name,
  ipt.plasmid_id as injected_plasmid_id,
  p1.name as injected_plasmid_name,
  irt.rna_id as injected_rna_id,
  r.name as injected_rna_name
from fish f
  left join fish_transgene_alleles fta on f.id_uuid = fta.fish_id
  left join transgene_alleles ta on fta.transgene_base_code = ta.transgene_base_code and fta.allele_number = ta.allele_number
  left join transgenes tg on ta.transgene_base_code = tg.transgene_base_code
  left join injected_plasmid_treatments ipt on f.id_uuid = ipt.fish_id
  left join plasmids p1 on ipt.plasmid_id = p1.id_uuid
  left join injected_rna_treatments irt on f.id_uuid = irt.fish_id
  left join rnas r on irt.rna_id = r.id_uuid;
