create table if not exists public.fish_pairs (
    id uuid primary key default gen_random_uuid(),
    mom_fish_id uuid not null references public.fish (id) on delete restrict,
    dad_fish_id uuid not null references public.fish (id) on delete restrict,
    created_by text,
    note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint chk_fish_pair_order check (mom_fish_id <= dad_fish_id),
    constraint uq_fish_pair unique (mom_fish_id, dad_fish_id)
);

create table if not exists public.tank_pairs (
    id uuid primary key default gen_random_uuid(),
    concept_id uuid references public.clutch_plans (id) on delete set null,
    fish_pair_id uuid not null references public.fish_pairs (id) on delete cascade,
    mother_tank_id uuid not null references public.containers (id) on delete restrict,
    father_tank_id uuid not null references public.containers (id) on delete restrict,
    status text not null default 'selected',
    created_by text,
    note text,
    created_at timestamptz not null default now(),
    updated_at timestamptz not null default now(),
    constraint uq_tank_pair_per_concept unique (concept_id, mother_tank_id, father_tank_id)
);

create index if not exists ix_fish_pairs_mom on public.fish_pairs (mom_fish_id);
create index if not exists ix_fish_pairs_dad on public.fish_pairs (dad_fish_id);
create index if not exists ix_tank_pairs_concept on public.tank_pairs (concept_id);
create index if not exists ix_tank_pairs_mother on public.tank_pairs (mother_tank_id);
create index if not exists ix_tank_pairs_father on public.tank_pairs (father_tank_id);

create or replace view public.v_tank_pairs as
select
    tp.id,
    tp.concept_id,
    tp.status,
    tp.created_by,
    tp.created_at,
    fp.id as fish_pair_id,
    mf.fish_code as mom_fish_code,
    df.fish_code as dad_fish_code,
    tp.mother_tank_id,
    mt.tank_code as mom_tank_code,
    tp.father_tank_id,
    dt.tank_code as dad_tank_code,
    coalesce(cp.clutch_code, cp.id::text) as clutch_code
from public.tank_pairs AS tp
inner join public.fish_pairs AS fp on tp.fish_pair_id = fp.id
inner join public.fish AS mf on fp.mom_fish_id = mf.id
inner join public.fish AS df on fp.dad_fish_id = df.id
left join public.clutch_plans AS cp on tp.concept_id = cp.id
inner join public.containers AS mt on tp.mother_tank_id = mt.id
inner join public.containers AS dt on tp.father_tank_id = dt.id;
