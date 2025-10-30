BEGIN;

drop view if exists public.v_plasmids_rich cascade;

create or replace view public.v_plasmids_rich as
with links as (
  select
    p.code as plasmid_code,
    p.name as plasmid_name,
    p.nickname,
    p.resistance,
    p.supports_invitro_rna,
    p.notes,
    f.fusion_name,
    fl.fluor_name,
    t.tag_name,
    pf.position_in_plasmid
  from public.plasmids p
  left join public.plasmid_fusions pf on pf.plasmid_code = p.code
  left join public.fusions f on f.fusion_code = pf.fusion_code
  left join public.fluors  fl on fl.fluor_code = f.fluor_code
  left join public.tags    t  on t.tag_code   = f.tag_code
),
dedup as (
  select
    plasmid_code,
    plasmid_name,
    nickname,
    resistance,
    supports_invitro_rna,
    notes,
    fusion_name,
    fluor_name,
    tag_name,
    min(position_in_plasmid) as pos
  from links
  group by
    plasmid_code, plasmid_name, nickname, resistance, supports_invitro_rna, notes,
    fusion_name, fluor_name, tag_name
)
select
  d.plasmid_code,
  d.plasmid_name,
  d.nickname,
  d.resistance,
  d.supports_invitro_rna,
  d.notes,
  array_remove(array_agg(d.fusion_name order by d.pos nulls last, d.fusion_name), null) as fusion_names,
  array_remove(array_agg(distinct d.fluor_name order by d.fluor_name), null) as fluor_names,
  array_remove(array_agg(distinct d.tag_name order by d.tag_name), null)       as tag_names
from dedup d
group by
  d.plasmid_code, d.plasmid_name, d.nickname, d.resistance, d.supports_invitro_rna, d.notes;

COMMIT;
