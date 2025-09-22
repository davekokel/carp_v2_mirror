-- Normalize public.transgenes to expose a canonical text key: transgene_base_code
-- Then create transgene_alleles + fish_transgene_alleles referencing that key.

-- pgcrypto is available in Supabase; if not, this still guards it
create extension if not exists pgcrypto;

do $$
declare
  pk_col text;
  pk_type text;
begin
  -- If the target column already exists, nothing to do.
  if exists (
    select 1
    from information_schema.columns
    where table_schema='public' and table_name='transgenes'
      and column_name='transgene_base_code'
  ) then
    raise notice 'transgenes.transgene_base_code already exists';
  elsif exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='transgenes'
      and column_name='code'
  ) then
    execute 'alter table public.transgenes rename column "code" to transgene_base_code';
  elsif exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='transgenes'
      and column_name='name'
  ) then
    execute 'alter table public.transgenes rename column "name" to transgene_base_code';
  else
    -- Find current PK column (if any)
    select a.attname
         , case when c.data_type is null then format_type(a.atttypid, a.atttypmod) else c.data_type end
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

    if pk_col is not null and lower(pk_type) like 'text%' then
      -- If PK is already a text column, just rename it to our canonical name
      execute format('alter table public.transgenes rename column %I to transgene_base_code', pk_col);
    else
      -- Otherwise, add a text column and populate it from the best available source
      execute 'alter table public.transgenes add column transgene_base_code text';
      if pk_col is not null then
        -- cast PK to text (uuid/int → text)
        execute format('update public.transgenes set transgene_base_code = %I::text', pk_col);
      else
        -- last resort: synthesize stable-ish codes
        execute 'update public.transgenes set transgene_base_code = md5(gen_random_uuid()::text)';
      end if;
      -- ensure not null + uniqueness
      execute 'alter table public.transgenes alter column transgene_base_code set not null';
      -- prefer to make it the primary key if none exists; else at least unique
      if not exists (
        select 1 from pg_constraint con
        join pg_class t on t.oid = con.conrelid
        join pg_namespace n on n.oid = t.relnamespace
        where n.nspname=''public'' and t.relname=''transgenes'' and con.contype=''p''
      ) then
        execute 'alter table public.transgenes add constraint transgenes_pkey primary key (transgene_base_code)';
      else
        -- If there is already a PK on some other column, add a unique constraint on our code
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
    end if;
  end if;
end$$;

-- Now the dependent tables, idempotently.

create table if not exists public.transgene_alleles (
  transgene_base_code text not null,
  allele_number       text not null,
  description         text,
  constraint transgene_alleles_pk primary key (transgene_base_code, allele_number),
  constraint transgene_alleles_fk_transgene
    foreign key (transgene_base_code)
    references public.transgenes(transgene_base_code)
    on delete cascade
);

create table if not exists public.fish_transgene_alleles (
  fish_id             uuid not null,
  transgene_base_code text not null,
  allele_number       text not null,
  zygosity            text,
  constraint fish_transgene_alleles_pk
    primary key (fish_id, transgene_base_code, allele_number),
  constraint fish_transgene_alleles_fk_fish
    foreign key (fish_id) references public.fish(id) on delete cascade,
  constraint fish_transgene_alleles_fk_allele
    foreign key (transgene_base_code, allele_number)
    references public.transgene_alleles(transgene_base_code, allele_number)
    on delete cascade
);

-- Friendly reminder about legacy booleans:
do $$
begin
  if exists (
    select 1
    from information_schema.columns
    where table_schema='public' and table_name='fish'
      and column_name like 'has_%'
  ) then
    raise notice 'Consider migrating legacy has_* columns on public.fish to fish_transgene_alleles.';
  end if;
end$$;
