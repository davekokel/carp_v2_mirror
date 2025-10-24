begin;

-- 1) Ensure nickname column is TEXT
alter table public.transgene_alleles
  alter column allele_nickname type text
  using allele_nickname::text;

-- 2) Drop partial unique index while we normalize/dedupe
drop index if exists uq_transgene_alleles_base_nickname;

-- 3) Normalize numeric-like nicknames '^\d+(\.0+)?$' to integer string (e.g., 301.0 -> 301)
update public.transgene_alleles
set allele_nickname = regexp_replace(allele_nickname, '\.0+$', '')
where allele_nickname ~ '^[0-9]+(\.0+)?$';

-- 4) Dedupe: keep the smallest allele_number per (base,nickname); move extra nicknames to their guN
with ranked as (
  select
    transgene_base_code,
    allele_number,
    allele_name,
    allele_nickname,
    row_number() over (
      partition by transgene_base_code, btrim(coalesce(allele_nickname,''))
      order by allele_number
    ) as rn
  from public.transgene_alleles
  where allele_nickname is not null and length(btrim(allele_nickname))>0
),
dupes as (
  select * from ranked where rn > 1
)
update public.transgene_alleles t
set allele_nickname = t.allele_name
from dupes d
where t.transgene_base_code = d.transgene_base_code
  and t.allele_number       = d.allele_number;

-- 5) Recreate partial unique index on (base, nickname) for non-empty nicknames
create unique index uq_transgene_alleles_base_nickname
  on public.transgene_alleles(transgene_base_code, allele_nickname)
  where allele_nickname is not null and length(btrim(allele_nickname)) > 0;

-- (Keep global numbering you already use — seq & default may already be present)
create sequence if not exists public.transgene_allele_number_seq;
select setval('public.transgene_allele_number_seq',
              coalesce((select max(allele_number) from public.transgene_alleles),0));
alter table public.transgene_alleles
  alter column allele_number set default nextval('public.transgene_allele_number_seq');

create unique index if not exists uq_transgene_alleles_number
  on public.transgene_alleles(allele_number);

-- 6) Ensure base exists (FK-safe)
create or replace function public.fn_ensure_transgene_base(p_base text)
returns void
language plpgsql
as $$
declare v_base text := btrim(p_base);
begin
  if v_base is null or length(v_base)=0 then
    raise exception 'transgene_base_code is required';
  end if;
  insert into public.transgenes(transgene_base_code)
  select v_base
  where not exists (select 1 from public.transgenes where transgene_base_code=v_base);
end
$$;

-- 7) Reinstall ingest: reuse-first; store CSV nickname exactly as text (after normalizing 301.0 -> 301);
--    default nickname to guN only if CSV empty; race-safe insert.
drop function if exists public.fn_ingest_allele_row_csv(text, text);

create function public.fn_ingest_allele_row_csv(p_base text, p_nickname text)
returns int
language plpgsql
as $$
declare
  v_base text := btrim(p_base);
  v_raw  text := nullif(btrim(coalesce(p_nickname,'')), '');
  v_nick text := case
                   when v_raw is null then null
                   when v_raw ~ '^[0-9]+(\.0+)?$' then regexp_replace(v_raw, '\.0+$', '')
                   else v_raw
                 end;
  v_num  int;
  v_name text;
begin
  perform public.fn_ensure_transgene_base(v_base);

  -- REUSE if same (base,nickname) exists
  if v_nick is not null then
    select allele_number into v_num
    from public.transgene_alleles
    where transgene_base_code = v_base
      and btrim(coalesce(allele_nickname,'')) = v_nick
    limit 1;
    if v_num is not null then
      return v_num;
    end if;
  end if;

  -- CREATE (race-safe) and then resolve number
  insert into public.transgene_alleles(transgene_base_code, allele_nickname)
  values (v_base, v_nick)
  on conflict (transgene_base_code, allele_nickname)
    where allele_nickname is not null and length(btrim(allele_nickname))>0
    do nothing
  returning allele_number into v_num;

  if v_num is null then
    select allele_number into v_num
    from public.transgene_alleles
    where transgene_base_code = v_base
      and btrim(coalesce(allele_nickname,'')) = coalesce(v_nick,'')
    order by allele_number
    limit 1;
  end if;

  v_name := 'gu' || v_num::text;

  update public.transgene_alleles ta
     set allele_name     = coalesce(ta.allele_name, v_name),
         allele_nickname = case
                              when ta.allele_nickname is null or length(btrim(ta.allele_nickname))=0
                                then v_name
                              else ta.allele_nickname
                            end
   where ta.transgene_base_code = v_base
     and ta.allele_number       = v_num;

  return v_num;
end
$$;

commit;
