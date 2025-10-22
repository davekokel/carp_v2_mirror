\set ON_ERROR_STOP on
begin;
create or replace function public.fn_uuid_v4()
returns uuid
language sql
immutable
as $$
  select (
    substr(md5(random()::text || clock_timestamp()::text), 1, 8) || '-' ||
    substr(md5(random()::text || clock_timestamp()::text), 1, 4) || '-' ||
    '4' || substr(md5(random()::text || clock_timestamp()::text), 2, 3) || '-' ||
    substr('89ab', floor(random()*4)::int + 1, 1) || substr(md5(random()::text || clock_timestamp()::text), 2, 3) || '-' ||
    substr(md5(random()::text || clock_timestamp()::text), 1, 12)
  )::uuid
$$;
commit;
