-- Normalize column names/order for v_fish_standard_clean, then replace the view body.

do $$
declare
  tgt_names text[] := array[
    'fish_code',
    'name',
    'nickname',
    'genetic_background',
    'line_building_stage',
    'birth_date',
    'created_time',
    'created_by',
    'transgene_base_code',
    'allele_number',
    'allele_nickname',
    'allele_name',
    'transgene_pretty_nickname',
    'transgene_pretty_name',
    'genotype'
  ];
  cur_names text[];
  i int;
begin
  -- If the view exists, rename its columns by ordinal position to target names.
  if to_regclass('public.v_fish_standard_clean') is not null then
    select array_agg(column_name order by ordinal_position)
    into cur_names
    from information_schema.columns
    where table_schema='public' and table_name='v_fish_standard_clean';

    if cur_names is not null then
      for i in 1..least(array_length(cur_names,1), array_length(tgt_names,1)) loop
        if cur_names[i] is distinct from tgt_names[i] then
          execute format('alter view public.v_fish_standard_clean rename column %I to %I', cur_names[i], tgt_names[i]);
        end if;
      end loop;
    end if;
  end if;
end $$;

-- Now replace the view body with the corrected definition (same column names/order as tgt_names).
create or replace view public.v_fish_standard_clean
as
select
  f.fish_code,                             -- 1
  f.name,                                  -- 2
  f.nickname,                              -- 3
  f.genetic_background,                    -- 4
  f.line_building_stage,                   -- 5
  f.date_birth            as birth_date,   -- 6
  f.created_at            as created_time, -- 7
  f.created_by,                            -- 8
  fta.transgene_base_code,                 -- 9
  fta.allele_number,                       -- 10
  r.allele_nickname,                       -- 11
  ('gu'||fta.allele_number::text) as allele_name,                               -- 12 (derived)
  ('Tg('||fta.transgene_base_code||')'||coalesce(r.allele_nickname,'')) as transgene_pretty_nickname, -- 13
  ('Tg('||fta.transgene_base_code||')'||('gu'||fta.allele_number::text)) as transgene_pretty_name,   -- 14
  (
    select string_agg(
             'Tg('||fta2.transgene_base_code||')'||('gu'||fta2.allele_number::text),
             '; ' order by fta2.transgene_base_code, fta2.allele_number
           )
    from public.fish_transgene_alleles fta2
    where fta2.fish_id = f.id
  ) as genotype                                                                    -- 15
from public.fish f
left join public.fish_transgene_alleles fta
  on fta.fish_id = f.id
left join public.transgene_allele_registry r
  on r.transgene_base_code = fta.transgene_base_code
 and r.allele_number       = fta.allele_number;
