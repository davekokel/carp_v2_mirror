begin;

-- Columns we rely on (idempotent)
do $$
begin
  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='transgene_alleles' and column_name='allele_name'
  ) then
    alter table public.transgene_alleles add column allele_name text;
  end if;

  if not exists (
    select 1 from information_schema.columns
    where table_schema='public' and table_name='transgene_alleles' and column_name='allele_nickname'
  ) then
    alter table public.transgene_alleles add column allele_nickname text;
  end if;
end$$;

-- Uniqueness: (base, number)
do $$
begin
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and indexname='uq_transgene_alleles_base_num'
  ) then
    create unique index uq_transgene_alleles_base_num
      on public.transgene_alleles(transgene_base_code, allele_number);
  end if;
end$$;

-- Uniqueness: (base, nickname) when nickname present
do $$
begin
  if not exists (
    select 1 from pg_indexes
    where schemaname='public' and indexname='uq_transgene_alleles_base_nick'
  ) then
    create unique index uq_transgene_alleles_base_nick
      on public.transgene_alleles(transgene_base_code, allele_nickname)
      where allele_nickname is not null and length(btrim(allele_nickname)) > 0;
  end if;
end$$;

-- Helper: next allele number per base (used by BEFORE INSERT trigger)
create or replace function public.fn_next_allele_number(p_base text)
returns int
language plpgsql
as $$
declare
  v_next int;
begin
  perform 1 from public.transgene_alleles
   where transgene_base_code = p_base
   for update;
  select coalesce(max(allele_number), 0) + 1
    into v_next
  from public.transgene_alleles
  where transgene_base_code = p_base;
  return v_next;
end
$$;

-- BEFORE INSERT filler (only when allele_number is null)
create or replace function public.trg_transgene_alleles_bi_fill_number()
returns trigger
language plpgsql
as $$
begin
  if new.allele_number is null then
    new.allele_number := public.fn_next_allele_number(new.transgene_base_code);
  end if;
  return new;
end
$$;

do $$
begin
  if exists (
    select 1 from pg_trigger
    where tgrelid='public.transgene_alleles'::regclass
      and tgname='trg_transgene_alleles_bi_fill_number'
  ) then
    drop trigger trg_transgene_alleles_bi_fill_number on public.transgene_alleles;
  end if;

  create trigger trg_transgene_alleles_bi_fill_number
    before insert on public.transgene_alleles
    for each row
    execute function public.trg_transgene_alleles_bi_fill_number();
end$$;

-- Canonical CSV ingest: precise rules you confirmed
-- Inputs: p_base (required), p_nickname (text, may be null/empty)
-- Output: the resolved allele_number (int) for (base, nickname)
create or replace function public.fn_ingest_allele_row_csv(p_base text, p_nickname text)
returns int
language plpgsql
as $$
declare
  v_base text := btrim(p_base);
  v_nick text := nullif(btrim(coalesce(p_nickname,'')), '');
  v_num  int;
begin
  if v_base is null or length(v_base)=0 then
    raise exception 'transgene_base_code is required';
  end if;

  -- If nickname present and already exists for this base, reuse its number
  if v_nick is not null then
    select allele_number into v_num
    from public.transgene_alleles
    where transgene_base_code = v_base
      and allele_nickname = v_nick
    limit 1;

    if v_num is not null then
      return v_num;
    end if;
  end if;

  -- Insert a new allele row; BI trigger assigns allele_number when null
  insert into public.transgene_alleles (transgene_base_code, allele_number, allele_nickname)
  values (v_base, null, v_nick)
  returning allele_number into v_num;

  -- Set canonical allele_name = 'gu' || allele_number (first assignment only)
  update public.transgene_alleles ta
     set allele_name = coalesce(ta.allele_name, 'gu' || v_num::text)
   where ta.transgene_base_code = v_base
     and ta.allele_number = v_num;

  return v_num;
end
$$;

commit;
