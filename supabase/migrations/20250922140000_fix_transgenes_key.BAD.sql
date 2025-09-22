-- Ensure public.transgenes exposes a canonical text key: transgene_base_code.
-- Works whether you currently have code/name/some-other-PK.

do $$
declare
  pk_col  text;
  pk_type text;
begin
  -- 1) If transgene_base_code already exists, nothing to do.
  if exists (
    select 1
    from information_schema.columns
    where table_schema='public' and table_name='transgenes'
      and column_name='transgene_base_code'
  ) then
    raise notice 'transgenes.transgene_base_code already exists';
    return;
  end if;

  -- 2) Prefer to rename a likely column to our canonical name.
  if exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='transgenes' and column_name='code'
  ) then
    execute 'alter table public.transgenes rename column "code" to transgene_base_code';
  elsif exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='transgenes' and column_name='name'
  ) then
    execute 'alter table public.transgenes rename column "name" to transgene_base_code';
  else
    -- 3) Otherwise, derive from current PK or synthesize.
    select a.attname,
           coalesce(c.data_type, format_type(a.atttypid, a.atttypmod))
      into pk_col, pk_type
    from pg_constraint con
    join pg_class t on t.oid = con.conrelid
    join pg_namespace n on n.oid = t.relnamespace
    join unnest(con.conkey) with ordinality as k(attnum, ord) on true
    join pg_attribute a on a.attrelid = t.oid and a.attnum = k.attnum
    left join information_schema.columns c
      on c.table_schema = n.nspname and c.table_name = t.relname and c.column_name = a.attname
    where n.nspname='public' and t.relname='transgenes' and con.contype='p'
    order by k.ord
    limit 1;

    execute 'alter table public.transgenes add column transgene_base_code text';

    if pk_col is not null then
      execute format('update public.transgenes set transgene_base_code = %I::text', pk_col);
    else
      -- last resort: stable-ish synthesized code
      execute 'create extension if not exists pgcrypto';
      execute 'update public.transgenes set transgene_base_code = md5(gen_random_uuid()::text)';
    end if;

    execute 'alter table public.transgenes alter column transgene_base_code set not null';
  end if;

  -- 4) Make sure it’s constrained (PK if none exists; otherwise UNIQUE).
  if not exists (
    select 1 from pg_constraint con
    join pg_class t on t.oid = con.conrelid
    join pg_namespace n on n.oid = t.relnamespace
    where n.nspname=''public'' and t.relname=''transgenes'' and con.contype=''p''
  ) then
    execute 'alter table public.transgenes add constraint transgenes_pkey primary key (transgene_base_code)';
  else
    if not exists (
      select 1 from pg_constraint con
      join pg_class t on t.oid = con.conrelid
      join pg_namespace n on n.oid = t.relnamespace
      where n.nspname=''public'' and t.relname=''transgenes'' and con.contype=''u''
        and pg_get_constraintdef(con.oid) like ''UNIQUE (transgene_base_code)''
    ) then
      execute 'alter table public.transgenes add constraint transgenes_transgene_base_code_key unique (transgene_base_code)';
    end if;
  end if;
end$$;
