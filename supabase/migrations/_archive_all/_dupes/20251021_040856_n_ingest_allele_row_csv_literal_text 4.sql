begin;

-- Ensure nickname column is pure text
alter table public.transgene_alleles
  alter column allele_nickname type text
  using allele_nickname::text;

-- Drop any old partial unique index
drop index if exists uq_transgene_alleles_base_nickname;

-- Clean any numeric-style nicknames (301.0 → 301)
update public.transgene_alleles
set allele_nickname = regexp_replace(allele_nickname, '\.0+$', '')
where allele_nickname ~ '^[0-9]+(\.0+)?$';

-- Reinstate uniqueness for textual nicknames
create unique index uq_transgene_alleles_base_nickname
  on public.transgene_alleles(transgene_base_code, allele_nickname)
  where allele_nickname is not null and length(btrim(allele_nickname)) > 0;

-- Replace the ingest function: reuse-first; literal text nickname
drop function if exists public.fn_ingest_allele_row_csv(text, text);

create or replace function public.fn_ingest_allele_row_csv(p_base text, p_nickname text)
returns integer
language plpgsql
as $$
declare
  v_base text := btrim(p_base);
  v_raw  text := btrim(coalesce(p_nickname,''));
  v_nick text := nullif(v_raw,'');
  v_num  int;
  v_name text;
begin
  perform public.fn_ensure_transgene_base(v_base);

  -- normalize numeric-looking nicknames to text form (301.0 -> 301)
  if v_nick is not null and v_nick ~ '^[0-9]+(\.0+)?$' then
    v_nick := regexp_replace(v_nick, '\.0+$', '');
  end if;

  -- reuse if exists
  select allele_number into v_num
  from public.transgene_alleles
  where transgene_base_code = v_base
    and btrim(coalesce(allele_nickname,'')) = coalesce(v_nick,'')
  limit 1;

  if v_num is not null then
    return v_num;
  end if;

  -- otherwise insert new
  insert into public.transgene_alleles(transgene_base_code, allele_nickname)
  values (v_base, v_nick)
  on conflict (transgene_base_code, allele_nickname)
    where allele_nickname is not null and length(btrim(allele_nickname)) > 0
    do nothing
  returning allele_number into v_num;

  if v_num is null then
    select allele_number into v_num
    from public.transgene_alleles
    where transgene_base_code = v_base
      and btrim(coalesce(allele_nickname,'')) = coalesce(v_nick,'')
    limit 1;
  end if;

  v_name := 'gu' || v_num::text;

  update public.transgene_alleles
     set allele_name = coalesce(allele_name, v_name),
         allele_nickname = coalesce(allele_nickname, v_name)
   where transgene_base_code = v_base
     and allele_number = v_num;

  return v_num;
end
$$;

commit;
