begin;
create or replace view public.v_fish_overview_all as
select
  f.id              as fish_id,
  f.fish_code,
  f.name,
  f.nickname,
  f.date_birth      as birthday,
  f.genetic_background,
  f.description,
  f.notes,
  f.created_at,
  f.updated_at
from public.fish f;
commit;
