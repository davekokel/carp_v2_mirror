begin;

-- 1) canonical fish-level allele link table
create table if not exists public.fish_transgene_alleles (
    fish_id             uuid not null
                           references public.fish_instances_v10(id)
                           on delete cascade,
    transgene_base_code text not null
                           references public.transgenes(transgene_base_code)
                           on delete restrict,
    allele_number       integer not null
                           references public.transgene_alleles(allele_number)
                           on delete restrict,
    created_at          timestamptz not null default now(),
    constraint pk_fish_transgene_alleles
        primary key (fish_id, transgene_base_code, allele_number)
);

comment on table public.fish_transgene_alleles is
  'Per-fish transgene alleles (v11). Populated at load time by v11 fish loaders.';

-- 2) view: allele rollups per fish_instance (no backfill, no DISTINCT)
drop view if exists public.v11_fish_allele_rollups;

create view public.v11_fish_allele_rollups as
select
    fi.id as fish_instance_id,
    string_agg(
        format('%s:%s',
            ta.transgene_base_code,
            coalesce(ta.allele_name, ta.allele_number::text)
        ),
        '; ' order by ta.transgene_base_code, ta.allele_number
    ) as allele_canonical_rollup,
    string_agg(
        format('Tg(%s)%s',
            ta.transgene_base_code,
            coalesce(ta.allele_name, ta.allele_number::text)
        ),
        '; ' order by ta.transgene_base_code, ta.allele_number
    ) as allele_label_rollup
from public.fish_instances_v10 fi
left join public.fish_transgene_alleles fta
       on fta.fish_id = fi.id
left join public.transgene_alleles ta
       on ta.transgene_base_code = fta.transgene_base_code
      and ta.allele_number       = fta.allele_number
group by fi.id;

comment on view public.v11_fish_allele_rollups is
  'Per-fish allele rollups (canonical base:allele and Tg(base)allele labels) for v11 fish instances.';

commit;
