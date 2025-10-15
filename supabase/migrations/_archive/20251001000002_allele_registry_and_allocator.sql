-- 20251001_allele_registry_and_allocator.sql
-- Canonical allele registry per transgene_base_code + allocator function.
-- Goal: DB assigns real allele_number; legacy labels are metadata.

begin;

-- 1) Registry table (idempotent)
create table if not exists public.transgene_allele_registry (
  base_code      text    not null,
  allele_number  integer not null,
  legacy_label   text,
  created_at     timestamptz not null default now(),
  primary key (base_code, allele_number)
);

-- Optional: keep legacy labels unique per base_code (NULLs allowed multiple);
DO 28762
begin
  if not exists (
    select 1
    from pg_indexes
    where schemaname='public'
      and indexname='uniq_registry_base_legacy'
  ) then
    execute 'create unique index uniq_registry_base_legacy
             on public.transgene_allele_registry (base_code, legacy_label)';
  end if;
end$$;

-- Helpful indexes
create index if not exists ix_registry_base_code
  on public.transgene_allele_registry (base_code);

-- 2) Allocation function (resolve or allocate a canonical integer)
create or replace function public.allocate_allele_number(p_base_code text, p_legacy_label text default null)
returns integer
language plpgsql
as $$
declare
  v_num integer;
begin
  if p_base_code is null or btrim(p_base_code) = '' then
    raise exception 'allocate_allele_number(): base_code is required';
  end if;

  -- If a legacy label maps already, return its canonical number.
  if p_legacy_label is not null and btrim(p_legacy_label) <> '' then
    select allele_number into v_num
    from public.transgene_allele_registry
    where base_code = p_base_code
      and legacy_label = p_legacy_label;
    if found then
      return v_num;
    end if;
  end if;

  -- Allocate next free number for this base_code (concurrency-safe).
  loop
    select coalesce(max(allele_number), 0) + 1
      into v_num
    from public.transgene_allele_registry
    where base_code = p_base_code;

    begin
      insert into public.transgene_allele_registry(base_code, allele_number, legacy_label)
      values (p_base_code, v_num, nullif(p_legacy_label,''));
      return v_num;
    exception when unique_violation then
      -- racing with another allocator; try again
      continue;
    end;
  end loop;
end
$$;

commit;
