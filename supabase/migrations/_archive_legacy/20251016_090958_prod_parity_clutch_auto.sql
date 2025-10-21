begin;

alter table if exists public.clutch_instances
add column if not exists birthday date,
add column if not exists created_by text;

alter table if exists public.clutches
add column if not exists clutch_code text;

create or replace function public.ensure_clutch_for_cross_instance()
returns trigger
language plpgsql
as $$
declare has_created_by boolean;
begin
  select exists (
    select 1 from information_schema.columns  where table_schema='public' and table_name='clutch_instances' and column_name='created_by'
  ) into has_created_by;

  if exists (select 1 from public.clutch_instances  where cross_instance_id = new.id) then
    return new;
  end if;

  if has_created_by then
    insert into public.clutch_instances (cross_instance_id, birthday, created_by)
    values (new.id, coalesce(new.cross_date, current_date), coalesce(new.created_by, 'system'));
  else
    insert into public.clutch_instances (cross_instance_id, birthday)
    values (new.id, coalesce(new.cross_date, current_date));
  end if;

  return new;
end $$;

do $$
begin
  if not exists (
    select 1
    from pg_trigger  where tgname='trg_cross_instance_auto_clutch'
  ) then
    execute $t$
      create trigger trg_cross_instance_auto_clutch
      after insert on public.cross_instances
      for each row execute function public.ensure_clutch_for_cross_instance()
    $t$;
  end if;
end$$;

create unique index if not exists uq_clutches_run_code
on public.clutches (cross_instance_id, coalesce(clutch_code, ''));

commit;
