-- Add allele_nickname / allele_name, auto-generate allele_number, and extend clean view with pretty fields.

-- 1) Extend allele table (idempotent)
alter table public.transgene_alleles
add column if not exists allele_nickname text,
add column if not exists allele_name text;

-- 2) Trigger to auto-fill allele_number & allele_name; keep nickname as text
create or replace function public.transgene_alleles_autofill()
returns trigger
language plpgsql
as $$
declare
  next_n int;
begin
  -- Treat nickname purely as text (no coercion needed)

  -- Generate allele_number if missing/blank
  if coalesce(nullif(new.allele_number::text, ''), '') = '' then
    select coalesce(max((nullif(allele_number, '')::int)),0)+1
      into next_n
    from public.transgene_alleles  where transgene_base_code = new.transgene_base_code
      and allele_number ~ '^\d+$';
    new.allele_number := next_n::text;
  end if;

  -- Always set allele_name = 'gu' || allele_number
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
'On insert/update: generate allele_number per base if missing; set allele_name = ''gu''||allele_number; store nickname as text.';

-- 3) Update clean view to expose nickname/number/name and pretty strings (no background in rollup)
create or replace view public.v_fish_standard_clean as
with vs as (
    select * from public.vw_fish_standard
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
        ta.allele_label as allele_label_canon,
        ta.allele_name as allele_name_canon
    from src AS s
    left join public.transgene_alleles AS ta
        on
            nullif(s.transgene_base, '') is not null
            and (nullif(s.allele_token, '') is not null or s.allele_token is null)
            and s.transgene_base = ta.transgene_base_code
            and (
                (ta.allele_number::text = s.allele_token::text)
                or (s.allele_token is null and ta.allele_number is not null)
            )
),

fmt as (
    select
        fish_code,
        genotype,
        genetic_background,
        birthday,
        transgene_base,
        nullif(allele_token, '') as allele_token,
        -- prefer canonical values; fallback to tokens/view
        coalesce(allele_number_canon, nullif(allele_token, '')) as allele_number,
        coalesce(allele_label_canon, nullif(allele_label_view, ''), '') as allele_label,
        coalesce(
            allele_name_canon, case when nullif(allele_token, '') is not null then 'gu' || allele_token else '' end
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
                                                when
                                                    nullif(
                                                        coalesce(allele_label_canon, allele_label_view, ''), ''
                                                    ) is not null
                                                    then ' ' || coalesce(allele_label_canon, allele_label_view, '')
                                                else ''
                                            end
                                            || ')'
                                    else ''
                                end
                    end
                ), '\s+', ' ', 'g'
            )
        ) as genotype_rollup_clean,
        -- pretty strings requested
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
'Clean fish standard view — includes allele_nickname/allele_number/allele_name and pretty strings; rollup excludes background.';

-- 4) Keep search wired to clean fields if present; refresh MV if present
do $$
begin
  if exists (
    select 1 from information_schema.views  where table_schema='public' and table_name='v_fish_search'
  ) then
    execute $vfs$
      create or replace view public.v_fish_search as
      select f.fish_code,
             lower(coalesce(sc.genotype, '') || ' ' || coalesce(sc.genetic_background, '')) as txt,
             coalesce(sc.genotype, '')           as genotype,
             coalesce(sc.genetic_background, '') as genetic_background,
             coalesce(l.n_live,0)               as n_live
      from public.fish AS f
      left join public.v_fish_live_counts AS l on l.fish_code = f.fish_code
      left join public.v_fish_standard_clean AS sc on sc.fish_code = f.fish_code;
    $vfs$;
  end if;
end$$;

-- Refresh materialized search view if helper exists
do $$
declare fn_exists boolean;
begin
  select exists(
    select 1 from pg_proc AS p join pg_namespace AS n on n.oid=p.pronamespace
    where n.nspname='public' and p.proname='refresh_mv_fish_search'
  ) into fn_exists;
  if fn_exists then
    perform public.refresh_mv_fish_search();
  end if;
end$$;
