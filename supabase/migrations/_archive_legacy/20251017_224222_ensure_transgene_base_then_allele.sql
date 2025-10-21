-- Ensure the transgene base exists before upserting an allele.

-- helper: create the base row if missing (assumes only base code is required or
-- other columns are nullable / have defaults; adjust if your schema differs).
create or replace function public.ensure_transgene_base(p_base text)
returns void
language plpgsql
as $$
begin
  if coalesce(nullif(p_base, ''), '') is null then
    return;
  end if;
  -- Try insert; ignore if already present
  begin
    insert into public.transgenes (transgene_base_code)
    values (p_base)
    on conflict (transgene_base_code) do nothing;
  exception when undefined_table then
    -- If the table doesn't exist in this env, do nothing.
    null;
  end;
end;
$$;

comment on function public.ensure_transgene_base(text) is
'Insert transgene base if missing (no-op if present).';

-- keep sequence (idempotent)
create sequence if not exists public.transgene_allele_number_seq;

-- trigger: keep integer allele_number + derived allele_name (idempotent)
create or replace function public.transgene_alleles_autofill()
returns trigger
language plpgsql
as $$
begin
  if new.allele_number is null then
    new.allele_number := nextval('public.transgene_allele_number_seq')::int;
  end if;
  new.allele_name := 'gu' || new.allele_number::text;
  return new;
end;
$$;

drop trigger if exists trg_transgene_alleles_autofill on public.transgene_alleles;
create trigger trg_transgene_alleles_autofill
before insert or update on public.transgene_alleles
for each row execute procedure public.transgene_alleles_autofill();

-- unique index on integer column (idempotent)
do $$
begin
  if not exists (
    select 1 from pg_indexes  where schemaname='public' and indexname='ux_transgene_alleles_number_int'
  ) then
    create unique index ux_transgene_alleles_number_int
      on public.transgene_alleles (allele_number);
  end if;
end$$;

-- redefine ensure_transgene_allele to ensure base, reuse, then mint
drop function if exists public.ensure_transgene_allele(text, text);
create or replace function public.ensure_transgene_allele(
    in p_transgene_base_code text,
    in p_allele_nickname text,
    out ret_allele_number text
) language plpgsql as $$
declare
  v_nick    text := nullif(btrim(p_allele_nickname), '');
  v_num_int int  := null;
begin
  -- 0) ensure base exists to satisfy FK
  perform public.ensure_transgene_base(p_transgene_base_code);

  -- 1) reuse by nickname (global)
  if v_nick is not null and lower(v_nick) <> 'new' then
    select ta.allele_number
      into v_num_int
    from public.transgene_alleles AS ta
    where ta.allele_nickname = v_nick
    limit 1;

    -- 1b) if not found and nickname is digits, reuse by number (global)
    if v_num_int is null and v_nick ~ '^\d+$' then
      select ta.allele_number
        into v_num_int
      from public.transgene_alleles AS ta
      where ta.allele_number = v_nick::int
      limit 1;
    end if;
  end if;

  -- 2) mint if still null
  if v_num_int is null then
    v_num_int := nextval('public.transgene_allele_number_seq')::int;
  end if;

  -- 3) upsert base+number; set nickname if provided
  insert into public.transgene_alleles(transgene_base_code, allele_number, allele_nickname)
  values (p_transgene_base_code, v_num_int, v_nick)
  on conflict (transgene_base_code, allele_number) do update
    set allele_nickname = coalesce(excluded.allele_nickname, public.transgene_alleles.allele_nickname);

  ret_allele_number := v_num_int::text;
  return;
end;
$$;

comment on function public.ensure_transgene_allele(text, text) is
'Ensures base exists; reuses allele by nickname/number globally; mints only if no match. Inserts integer allele_number; returns text.';
