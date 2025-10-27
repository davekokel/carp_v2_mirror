create or replace view public.v_rna_plasmids as
select
  code,
  name,
  nickname,
  created_at,
  created_by
from public.plasmids
where coalesce(supports_invitro_rna, false) = true;
