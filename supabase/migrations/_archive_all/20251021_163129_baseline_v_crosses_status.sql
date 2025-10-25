begin;

-- v_crosses_status: status keyed by the tank pair id
-- Only columns required by downstream views: id, status (created_* are nice to have)
create or replace view public.v_crosses_status as
select
  tp.id                           as id,          -- joins to pair_id
  coalesce(tp.status, 'draft')    as status,
  tp.created_by,
  tp.created_at
from public.tank_pairs tp;

commit;
