-- Ensure allele_number is handled as INTEGER in the table and function.
-- Fix ensure_transgene_allele to insert integer allele_number; still return text to callers.

-- 1) Global sequence (idempotent)
create sequence if not exists public.transgene_allele_number_seq;

-- 2) Unique index directly on the integer column (idempotent)
do $$
begin
  if not exists (
    select 1 from pg_indexes  where schemaname='public' and indexname='ux_transgene_alleles_number_int'
  ) then
    -- If an old expression-based index exists, keep it; this one is the canonical unique
    create unique index ux_transgene_alleles_number_int
      on public.transgene_alleles (allele_number);
  end if;
end$$;

-- 3) Trigger: if allele_number is NULL, fill from global AS sequence; always set allele_name='gu'||allele_number
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

comment on function public.transgene_alleles_autofill() is
'Fill allele_number from global AS sequence iff NULL; set allele_name=''gu''||allele_number.';

-- 4) Function: reuse-by-nickname or number; otherwise mint.
--    Use INTEGER internally; return TEXT externally for UI continuity.
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
  -- Reuse by nickname (global)
  if v_nick is not null and lower(v_nick) <> 'new' then
    select ta.allele_number
      into v_num_int
    from public.transgene_alleles AS ta
    where ta.allele_nickname = v_nick
    limit 1;

    -- If not found and nickname is all digits, reuse by number (global)
    if v_num_int is null and v_nick ~ '^\d+$' then
      select ta.allele_number
        into v_num_int
      from public.transgene_alleles AS ta
      where ta.allele_number = v_nick::int
      limit 1;
    end if;
  end if;

  -- If still null, mint from global AS sequence
  if v_num_int is null then
    v_num_int := nextval('public.transgene_allele_number_seq')::int;
  end if;

  -- Upsert base+number; set nickname if provided (do not overwrite with NULL)
  insert into public.transgene_alleles(transgene_base_code, allele_number, allele_nickname)
  values (p_transgene_base_code, v_num_int, v_nick)
  on conflict (transgene_base_code, allele_number) do update
    set allele_nickname = coalesce(excluded.allele_nickname, public.transgene_alleles.allele_nickname);

  ret_allele_number := v_num_int::text;
  return;
end;
$$;

comment on function public.ensure_transgene_allele(text, text) is
'Reuses allele by nickname or number (global); mints from global AS sequence only if no match. Inserts integer allele_number; returns text.';
