-- Harden ensure_transgene_allele(): reuse by nickname or number globally before minting.
-- Keep trigger to fill allele_number only if still blank.

-- 1) Global unique index (idempotent)
do $$
begin
  if not exists (
    select 1 from pg_indexes  where schemaname='public' and indexname='ux_transgene_alleles_number'
  ) then
    create unique index ux_transgene_alleles_number
      on public.transgene_alleles ((nullif(allele_number::text, '')));
  end if;
end$$;

-- 2) Sequence exists (idempotent)
create sequence if not exists public.transgene_allele_number_seq;

-- 3) Trigger stays the same: only fill if blank
create or replace function public.transgene_alleles_autofill()
returns trigger
language plpgsql
as $$
begin
  if coalesce(nullif(new.allele_number::text, ''), '') = '' then
    new.allele_number := nextval('public.transgene_allele_number_seq')::text;
  end if;
  new.allele_name := 'gu' || coalesce(new.allele_number::text, '');
  return new;
end;
$$;

drop trigger if exists trg_transgene_alleles_autofill on public.transgene_alleles;
create trigger trg_transgene_alleles_autofill
before insert or update on public.transgene_alleles
for each row
execute procedure public.transgene_alleles_autofill();

comment on function public.transgene_alleles_autofill() is
'Fill allele_number from global AS sequence iff blank; allele_name := ''gu''||allele_number.';

-- 4) Redefine ensure_transgene_allele(): reuse by nickname or number before mint.
--    Returns ret_allele_number (text).
drop function if exists public.ensure_transgene_allele(text, text);
create or replace function public.ensure_transgene_allele(
    in p_transgene_base_code text,
    in p_allele_nickname text,
    out ret_allele_number text
) language plpgsql as $$
declare
  v_nick text := nullif(btrim(p_allele_nickname), '');
  v_num  text := null;
begin
  -- 1) Try reuse by nickname (global)
  if v_nick is not null and lower(v_nick) <> 'new' then
    select ta.allele_number::text
      into v_num
    from public.transgene_alleles AS ta
    where ta.allele_nickname = v_nick
    limit 1;

    -- 2) If not found and nickname is all digits, try reuse by allele_number (global)
    if v_num is null and v_nick ~ '^\d+$' then
      select ta.allele_number::text
        into v_num
      from public.transgene_alleles AS ta
      where ta.allele_number::text = v_nick
      limit 1;
    end if;
  end if;

  -- 3) If still null, mint from global AS sequence
  if v_num is null then
    v_num := nextval('public.transgene_allele_number_seq')::text;
  end if;

  -- 4) Upsert the allele row for this base+number; set/keep nickname when provided
  insert into public.transgene_alleles(transgene_base_code, allele_number, allele_nickname)
  values (p_transgene_base_code, v_num, v_nick)
  on conflict (transgene_base_code, allele_number) do update
    set allele_nickname = coalesce(excluded.allele_nickname, public.transgene_alleles.allele_nickname);

  ret_allele_number := v_num;
  return;
end;
$$;

comment on function public.ensure_transgene_allele(text, text) is
'Reuses allele by nickname or allele_number (global). Mints from global AS sequence only if no match. Returns canonical allele_number.';
