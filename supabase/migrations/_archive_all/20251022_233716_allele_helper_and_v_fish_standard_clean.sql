create or replace function public.upsert_fish_allele_from_csv(
  v_fish_id uuid,
  v_base_code text,
  v_allele_nickname text
) returns void
language plpgsql as $$
declare
  v_num int;
  v_nick_final text;
begin
  if coalesce(v_base_code,'') = '' then
    return;
  end if;

  select r.allele_number
    into v_num
  from public.transgene_allele_registry r
  where r.transgene_base_code = v_base_code
    and coalesce(r.allele_nickname,'') = coalesce(v_allele_nickname,'')
  limit 1;

  if v_num is null then
    select coalesce(max(allele_number),0)+1
      into v_num
      from public.transgene_allele_registry;

    v_nick_final := coalesce(nullif(v_allele_nickname,''), 'gu'||v_num::text);

    insert into public.transgene_allele_registry(transgene_base_code, allele_number, allele_nickname, created_at)
    values (v_base_code, v_num, v_nick_final, now())
    on conflict do nothing;
  end if;

  insert into public.transgene_alleles(transgene_base_code, allele_number)
  values (v_base_code, v_num)
  on conflict do nothing;

  insert into public.fish_transgene_alleles(fish_id, transgene_base_code, allele_number)
  values (v_fish_id, v_base_code, v_num)
  on conflict do nothing;
end;
$$;

create or replace view public.v_fish_standard_clean as
select
  f.id                      as fish_id,
  f.fish_code,
  f.name,
  f.nickname,
  f.genetic_background,
  f.line_building_stage,
  f.date_birth              as birth_date,
  f.created_at              as created_time,
  f.created_by,
  fta.transgene_base_code,
  fta.allele_number,
  r.allele_nickname,
  ('gu' || fta.allele_number::text)                             as allele_name,
  ('Tg('||fta.transgene_base_code||')'||coalesce(r.allele_nickname,'')) as transgene_pretty_nickname,
  ('Tg('||fta.transgene_base_code||')'||('gu'||fta.allele_number::text)) as transgene_pretty_name,
  (
    select string_agg('Tg('||fta2.transgene_base_code||')'||('gu'||fta2.allele_number::text),
                      '; ' order by fta2.transgene_base_code, fta2.allele_number)
    from public.fish_transgene_alleles fta2
    where fta2.fish_id = f.id
  ) as genotype
from public.fish f
left join public.fish_transgene_alleles fta
  on fta.fish_id = f.id
left join public.transgene_allele_registry r
  on r.transgene_base_code = fta.transgene_base_code
 and r.allele_number       = fta.allele_number;
