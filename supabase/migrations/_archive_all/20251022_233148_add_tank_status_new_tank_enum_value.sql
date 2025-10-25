-- Add 'new_tank' to whatever enum is used by public.tank_status_history.status
do $$
declare
  t regtype;
  has boolean;
begin
  select a.atttypid::regtype
    into t
  from pg_attribute a
  where a.attrelid = 'public.tank_status_history'::regclass
    and a.attname  = 'status'
    and a.attnum  > 0;

  if t is null then
    raise notice 'Could not locate type of public.tank_status_history.status';
    return;
  end if;

  select exists (
    select 1 from pg_type ty
    join pg_enum e on e.enumtypid = ty.oid
    where ty.oid = t::oid and e.enumlabel = 'new_tank'
  ) into has;

  if not has then
    execute format('ALTER TYPE %s ADD VALUE %L', t::text, 'new_tank');
  end if;
end $$;
