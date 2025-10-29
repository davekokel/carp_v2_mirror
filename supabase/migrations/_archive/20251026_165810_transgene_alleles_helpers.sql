DROP FUNCTION IF EXISTS public.upsert_transgene_allele(text,text) CASCADE;
create sequence if not exists public.transgene_allele_number_seq start 1;

create table if not exists public.transgene_alleles (
  transgene_base_code text not null,
  allele_number int not null,
  allele_name text not null,
  allele_nickname text,
  created_at timestamptz not null default now(),
  primary key (transgene_base_code, allele_number)
);

create unique index if not exists uq_transgene_alleles_global_number
on public.transgene_alleles(allele_number);

create unique index if not exists uq_transgene_alleles_nickname_per_base
on public.transgene_alleles(transgene_base_code, allele_nickname)
where allele_nickname is not null;

create or replace function public.upsert_transgene_allele(p_base text, p_nickname_in text)
returns table(transgene_base_code text, allele_number int, allele_name text, allele_nickname text)
language plpgsql
as $$
declare
  v_nickname text := nullif(trim(p_nickname_in), '');
  v_num int;
  v_name text;
begin
  if v_nickname is not null then
    select ta.transgene_base_code, ta.allele_number, ta.allele_name, ta.allele_nickname
      into transgene_base_code, allele_number, allele_name, allele_nickname
    from public.transgene_alleles ta
    where ta.transgene_base_code = p_base
      and ta.allele_nickname = v_nickname
    limit 1;
    if found then
      return next;
      return;
    end if;
  end if;

  loop
    begin
      v_num := nextval('public.transgene_allele_number_seq')::int;
      v_name := 'gu' || v_num::text;
      insert into public.transgene_alleles(transgene_base_code, allele_number, allele_name, allele_nickname)
      values (p_base, v_num, v_name, coalesce(v_nickname, v_name))
      returning transgene_base_code, allele_number, allele_name, allele_nickname
      into transgene_base_code, allele_number, allele_name, allele_nickname;
      return next;
      return;
    exception
      when unique_violation then
        continue;
    end;
  end loop;
end
$$;

create or replace function public.link_fish_to_transgene_allele(p_fish_uuid uuid, p_base text, p_nickname text)
returns table(fish_uuid uuid, transgene_base_code text, allele_number int)
language plpgsql
as $$
declare
  r record;
begin
  select * into r from public.upsert_transgene_allele(p_base, p_nickname);
  insert into public.fish_transgene_alleles(fish_uuid, transgene_base_code, allele_number)
  values (p_fish_uuid, r.transgene_base_code, r.allele_number)
  on conflict do nothing;
  fish_uuid := p_fish_uuid;
  transgene_base_code := r.transgene_base_code;
  allele_number := r.allele_number;
  return next;
end
$$;
