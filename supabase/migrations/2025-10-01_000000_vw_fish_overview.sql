-- 20251001_vw_fish_overview.sql
-- A readable, join-ready overview of fish + genotype + injection treatments
begin;

create or replace view public.vw_fish_overview as
with genotype as (
  select
    fta.fish_id,
    string_agg(
      fta.transgene_base_code || ':' || fta.allele_number ||
      case when coalesce(nullif(fta.zygosity,''),'') <> '' then ' ('||fta.zygosity||')' else '' end,
      ', ' order by fta.transgene_base_code, fta.allele_number
    ) as genotype_text
  from public.fish_transgene_alleles fta
  group by fta.fish_id
),
rna_inj as (
  select
    irt.fish_id,
    max(t.performed_at) as last_rna_injection_at,
    string_agg(
      coalesce(r.rna_code,'(unknown)') ||
      coalesce(' '||irt.amount::text,'') ||
      coalesce(' '||irt.units,'') ||
      case when coalesce(nullif(irt.note,''),'') <> '' then ' ['||irt.note||']' else '' end ||
      coalesce(' @ '||to_char(t.performed_at,'YYYY-MM-DD'),'')
    , '; ' order by t.performed_at desc) as rna_injections_text
  from public.injected_rna_treatments irt
  join public.treatments t on t.id = irt.treatment_id
  left join public.rnas r on r.id_uuid = irt.rna_id
  group by irt.fish_id
),
plasmid_inj as (
  select
    ipt.fish_id,
    max(t.performed_at) as last_plasmid_injection_at,
    string_agg(
      coalesce(p.plasmid_code,'(unknown)') ||
      coalesce(' '||ipt.amount::text,'') ||
      coalesce(' '||ipt.units,'') ||
      case when coalesce(nullif(ipt.note,''),'') <> '' then ' ['||ipt.note||']' else '' end ||
      coalesce(' @ '||to_char(t.performed_at,'YYYY-MM-DD'),'')
    , '; ' order by t.performed_at desc) as plasmid_injections_text
  from public.injected_plasmid_treatments ipt
  join public.treatments t on t.id = ipt.treatment_id
  left join public.plasmids p on p.id_uuid = ipt.plasmid_id
  group by ipt.fish_id
)
select
  f.id                                as fish_id,
  f.name                              as fish_name,
  f.batch_label,
  f.line_building_stage,
  f.nickname,
  f.strain,
  f.date_of_birth,
  f.description,
  coalesce(g.genotype_text,'')             as genotype_text,
  coalesce(rna.rna_injections_text,'')     as rna_injections_text,
  coalesce(plasmid.plasmid_injections_text,'') as plasmid_injections_text,
  greatest(rna.last_rna_injection_at, plasmid.last_plasmid_injection_at) as last_treatment_at,
  now()                               as generated_at
from public.fish f
left join genotype    g       on g.fish_id = f.id
left join rna_inj     rna     on rna.fish_id = f.id
left join plasmid_inj plasmid on plasmid.fish_id = f.id;

commit;
