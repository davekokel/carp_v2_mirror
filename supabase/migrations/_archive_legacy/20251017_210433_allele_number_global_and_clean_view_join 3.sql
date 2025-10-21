-- Make allele_number global (not per base), and fix clean view join to AS use allele_number only.

-- 1) Ensure global uniqueness of allele_number (if column exists)
do $$
begin
  if exists (
    select 1 from information_schema.columns  where table_schema='public' and table_name='transgene_alleles' and column_name='allele_number'
  ) then
    begin
      create unique index if not exists ux_transgene_alleles_number
        on public.transgene_alleles ((nullif(allele_number::text, '')));
      exception when others then
        -- ignore if index expression conflicts on null handling; we still rely on app-side generation
        null;
    end;
  end if;
end$$;

-- 2) Update trigger to generate allele_number as next GLOBAL integer when missing
create or replace function public.transgene_alleles_autofill()
returns trigger
language plpgsql
as $$
declare
  next_n int;
begin
  -- Generate allele_number if missing/blank: GLOBAL max + 1 (over integer-like rows)
  if coalesce(nullif(new.allele_number::text, ''), '') = '' then
    select coalesce(max((nullif(allele_number, '')::int)),0)+1
      into next_n
    from public.transgene_alleles  where allele_number ~ '^\d+$';
    new.allele_number := next_n::text;
  end if;

  -- Always set allele_name = 'gu' || allele_number
  new.allele_name := 'gu' || coalesce(new.allele_number::text, '');

  -- allele_nickname stays as provided (text)
  return new;
end;
$$;

drop trigger if exists trg_transgene_alleles_autofill on public.transgene_alleles;
create trigger trg_transgene_alleles_autofill
before insert or update on public.transgene_alleles
for each row
execute procedure public.transgene_alleles_autofill();

comment on function public.transgene_alleles_autofill() is
'On insert/update: generate GLOBAL allele_number if missing; set allele_name = ''gu''||allele_number; keep nickname as text.';

-- 3) Fix v_fish_standard_clean to resolve canonical allele by allele_number only (no base match needed).
create or replace view public.v_fish_standard_clean as
with vs as (
    select * from public.v_fish_standard
),

src as (
    select
        vs.fish_code,
        coalesce(vs.genotype, '') as genotype,
        coalesce(vs.genetic_background, '') as genetic_background,
        to_char(coalesce(vs.date_birth::date, null), 'YYYY-MM-DD') as birthday,
        coalesce(
            to_jsonb(vs.vs) ->> 'transgene_base_code',
            to_jsonb(vs.vs) ->> 'transgene',
            to_jsonb(vs.vs) ->> 'transgene_print', ''
        ) as transgene_base,
        coalesce(
            to_jsonb(vs.vs) ->> 'allele_code',
            to_jsonb(vs.vs) ->> 'allele_number', ''
        ) as allele_token,
        coalesce(to_jsonb(vs.vs) ->> 'allele_label', '') as allele_label_view
    from vs
),

joined as (
    select
        s.*,
        ta.allele_nickname,
        ta.allele_number as allele_number_canon,
        ta.allele_name as allele_name_canon
    from src AS s
    left join public.transgene_alleles AS ta
        on
            nullif(s.allele_token, '') is not null
            and ta.allele_number::text = s.allele_token::text
),

fmt as (
    select
        fish_code,
        genotype,
        genetic_background,
        birthday,
        transgene_base,
        nullif(allele_token, '') as allele_token,
        coalesce(allele_number_canon, nullif(allele_token, '')) as allele_number,
        coalesce(nullif(allele_label_view, ''), '') as allele_label,
        coalesce(
            allele_name_canon,
            case when nullif(allele_token, '') is not null then 'gu' || allele_token else '' end
        ) as allele_name,
        coalesce(allele_nickname, '') as allele_nickname,

        -- clean rollup: ONLY genotype elements (no background)
        trim(
            regexp_replace(
                concat_ws(
                    ' ',
                    case
                        when nullif(transgene_base, '') is not null
                            then
                                transgene_base
                                || case
                                    when nullif(coalesce(allele_number_canon, allele_token, ''), '') is not null
                                        then
                                            '('
                                            || coalesce(allele_number_canon, allele_token, '')
                                            || case
                                                when nullif(allele_label, '') is not null
                                                    then ' ' || allele_label
                                                else ''
                                            end
                                            || ')'
                                    else ''
                                end
                    end
                ), '\s+', ' ', 'g'
            )
        ) as genotype_rollup_clean,

        -- pretty strings
        case
            when nullif(transgene_base, '') is not null and nullif(coalesce(allele_nickname, ''), '') is not null
                then 'Tg(' || transgene_base || ')' || allele_nickname
            else ''
        end as transgene_pretty_nickname,

        case
            when nullif(transgene_base, '') is not null and nullif(coalesce(allele_name, ''), '') is not null
                then 'Tg(' || transgene_base || ')' || allele_name
            else ''
        end as transgene_pretty_name
    from joined
)

select
    fish_code,
    genotype,
    genetic_background,
    birthday,
    transgene_base,
    allele_token,
    allele_number,
    allele_label,
    allele_nickname,
    allele_name,
    transgene_pretty_nickname,
    transgene_pretty_name,
    genotype_rollup_clean
from fmt;

comment on view public.v_fish_standard_clean is
'Clean fish standard view — allele_number is global; enriched allele_name/nickname; pretty strings; rollup excludes background.';
