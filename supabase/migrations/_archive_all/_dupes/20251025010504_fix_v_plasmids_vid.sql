begin;

drop view if exists public.v_plasmids cascade;

create or replace view public.v_plasmids as
select
  p.id::uuid                    as vid,                -- required by Streamlit
  p.code::text                  as v_code,
  p.name::text                  as v_name,
  p.nickname::text              as v_nickname,
  p.fluors::text                as v_fluors,
  p.resistance::text            as v_resistance,
  p.supports_invitro_rna        as v_supports_invitro_rna,
  nullif(p.created_by,'')::text as v_created_by,
  p.notes::text                 as v_notes,
  p.created_at                  as v_created_at,
  null::uuid                    as v_rna_id,
  null::text                    as v_rna_code,
  null::text                    as v_rna_name
from public.plasmids p
left join public.plasmid_registry r
  on r.plasmid_code = p.code;

commit;
