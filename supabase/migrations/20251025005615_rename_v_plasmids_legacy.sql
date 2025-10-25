begin;

-- Drop any leftover old alias
drop view if exists public.v_plasmids cascade;

-- Recreate the legacy-named view
create or replace view public.v_plasmids as
select *
from public.v_plasmids_canonical;

commit;
