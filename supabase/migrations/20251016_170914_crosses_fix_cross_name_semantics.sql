BEGIN;

-- 1) Backfill: force cross_name to genetic "mom × dad" form
update public.crosses
set cross_name = public.gen_cross_name(mother_code, father_code);

-- 2) Replace trigger: cross_name is always the computed genetic name.
create or replace function public.trg_crosses_set_cross_name()
returns trigger
language plpgsql
as $$
begin
  new.cross_name := public.gen_cross_name(new.mother_code, new.father_code);
  return new;
end
$$;

drop trigger if exists crosses_set_names on public.crosses;
drop trigger if exists crosses_set_name  on public.crosses;

create trigger crosses_set_cross_name
before insert or update of mother_code, father_code
on public.crosses
for each row
execute function public.trg_crosses_set_cross_name();

-- keep cross_nickname totally independent (no changes needed)

COMMIT;
