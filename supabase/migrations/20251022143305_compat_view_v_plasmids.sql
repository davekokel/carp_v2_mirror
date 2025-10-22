create or replace view public.v_plasmids as
select
  id,
  code,
  name,
  nickname,
  fluors,
  resistance,
  supports_invitro_rna,
  created_by,
  created_at,
  notes,
  rna_id,
  rna_code,
  rna_name
from public.vw_plasmids_overview;
