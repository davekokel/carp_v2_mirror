create extension if not exists pgcrypto;

create table if not exists public.transgene_allele_registry (
  transgene_base_code text not null,
  allele_number       integer not null,
  allele_name         text not null,
  allele_nickname     text,
  created_at          timestamptz default now(),
  created_by          text,
  primary key (transgene_base_code, allele_number)
);

create unique index if not exists u_transgene_base_nickname
  on public.transgene_allele_registry (transgene_base_code, coalesce(allele_nickname,''));

create sequence if not exists public.transgene_allele_number_seq start 1;

create or replace function public.ensure_allele(p_base text, p_nick text)
returns table (
  transgene_base_code text,
  allele_number integer,
  allele_name text,
  allele_nickname text
) language plpgsql as $$
declare
  v_num integer;
  v_name text;
  v_nick text := coalesce(p_nick,'');
begin
  if coalesce(p_base,'') = '' then
    return query select null::text, null::int, null::text, null::text; 
    return;
  end if;

  select r.allele_number, r.allele_name, r.allele_nickname
    into v_num, v_name, v_nick
  from public.transgene_allele_registry r
  where r.transgene_base_code = p_base
    and coalesce(r.allele_nickname,'') = v_nick
  limit 1;

  if v_num is null then
    select nextval('public.transgene_allele_number_seq')::int into v_num;
    v_name := 'gu' || v_num::text;
    insert into public.transgene_allele_registry(transgene_base_code, allele_number, allele_name, allele_nickname)
    values (p_base, v_num, v_name, nullif(v_nick,''))
    on conflict do nothing;
  end if;

  return query
  select p_base, v_num, v_name, nullif(v_nick,'');
end;
$$;

create or replace function public.upsert_fish_allele_from_csv(
  p_fish_id uuid,
  p_base text,
  p_nick text
)
returns table (
  transgene_base_code text,
  allele_number integer,
  allele_name text,
  allele_nickname text
) language plpgsql as $$
declare
  r record;
begin
  if coalesce(p_base,'') = '' then
    return;
  end if;

  for r in select * from public.ensure_allele(p_base, p_nick) loop
    insert into public.transgene_alleles(transgene_base_code, allele_number)
    values (r.transgene_base_code, r.allele_number)
    on conflict do nothing;

    insert into public.fish_transgene_alleles(fish_id, transgene_base_code, allele_number)
    values (p_fish_id, r.transgene_base_code, r.allele_number)
    on conflict do nothing;

    return query select r.transgene_base_code, r.allele_number, r.allele_name, r.allele_nickname;
  end loop;
end;
$$;

create or replace view public.v_fish_standard_clean as
select
  f.id as fish_id,
  f.fish_code,
  f.name,
  f.nickname,
  f.genetic_background,
  f.line_building_stage,
  f.date_birth as birth_date,
  f.created_at as created_time,
  f.created_by,
  ta.transgene_base_code,
  fta.allele_number,
  r.allele_nickname,
  r.allele_name,
  ('Tg('||fta.transgene_base_code||')'||coalesce(r.allele_nickname,''))::text as transgene_pretty_nickname,
  ('Tg('||fta.transgene_base_code||')'||coalesce(r.allele_name,''))::text      as transgene_pretty_name,
  (
    select string_agg('Tg('||fta2.transgene_base_code||')'||coalesce(r2.allele_name,''), '; ' order by fta2.transgene_base_code, r2.allele_name)
    from public.fish_transgene_alleles fta2
    join public.transgene_allele_registry r2
      on r2.transgene_base_code=fta2.transgene_base_code
     and r2.allele_number=fta2.allele_number
    where fta2.fish_id=f.id
  ) as genotype
from public.fish f
left join public.fish_transgene_alleles fta
  on fta.fish_id=f.id
left join public.transgene_alleles ta
  on ta.transgene_base_code=fta.transgene_base_code
 and ta.allele_number=fta.allele_number
left join public.transgene_allele_registry r
  on r.transgene_base_code=fta.transgene_base_code
 and r.allele_number=fta.allele_number;
