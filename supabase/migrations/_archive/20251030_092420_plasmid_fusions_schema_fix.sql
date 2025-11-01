BEGIN;

create table if not exists public.fluors (
  fluor_code text primary key,
  fluor_name text not null,
  color_family text,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.tags (
  tag_code text primary key,
  tag_name text not null,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now()
);

create table if not exists public.fusions (
  fusion_code text primary key,
  fusion_name text not null,
  fluor_code text not null references public.fluors(fluor_code) on update cascade on delete restrict,
  tag_code text null references public.tags(tag_code) on update cascade on delete restrict,
  notes text,
  created_at timestamptz not null default now(),
  updated_at timestamptz not null default now(),
  constraint uq_fusions_unique_combo unique (fusion_name, fluor_code, tag_code)
);

create table if not exists public.plasmid_fusions (
  plasmid_code text not null references public.plasmids(code) on update cascade on delete cascade,
  fusion_code text not null references public.fusions(fusion_code) on update cascade on delete restrict,
  position_in_plasmid int,
  primary key (plasmid_code, fusion_code)
);

create index if not exists idx_fusions_fluor on public.fusions(fluor_code);
create index if not exists idx_fusions_tag on public.fusions(tag_code);
create index if not exists idx_plasmid_fusions_plasmid on public.plasmid_fusions(plasmid_code);

create or replace function public.touch_updated_at()
returns trigger language plpgsql as $$
begin
  new.updated_at := now();
  return new;
end $$;

do $$
begin
  if not exists (select 1 from pg_trigger where tgname = 'trg_fluors_touch') then
    create trigger trg_fluors_touch before update on public.fluors
    for each row execute function public.touch_updated_at();
  end if;
  if not exists (select 1 from pg_trigger where tgname = 'trg_tags_touch') then
    create trigger trg_tags_touch before update on public.tags
    for each row execute function public.touch_updated_at();
  end if;
  if not exists (select 1 from pg_trigger where tgname = 'trg_fusions_touch') then
    create trigger trg_fusions_touch before update on public.fusions
    for each row execute function public.touch_updated_at();
  end if;
end $$;

create or replace view public.v_plasmids_rich as
with links as (
  select
    p.code as plasmid_code,
    p.name as plasmid_name,
    p.nickname,
    p.resistance,
    p.supports_invitro_rna,
    p.notes,
    f.fusion_name,
    fl.fluor_name,
    t.tag_name,
    pf.position_in_plasmid
  from public.plasmids p
  left join public.plasmid_fusions pf on pf.plasmid_code = p.code
  left join public.fusions f on f.fusion_code = pf.fusion_code
  left join public.fluors fl on fl.fluor_code = f.fluor_code
  left join public.tags t on t.tag_code = f.tag_code
),
dedup as (
  select
    plasmid_code,
    plasmid_name,
    nickname,
    resistance,
    supports_invitro_rna,
    notes,
    min(position_in_plasmid) as pos,
    fusion_name,
    fluor_name,
    tag_name
  from links
  group by
    plasmid_code, plasmid_name, nickname, resistance, supports_invitro_rna, notes,
    fusion_name, fluor_name, tag_name
)
select
  d.plasmid_code,
  d.plasmid_name,
  d.nickname,
  d.resistance,
  d.supports_invitro_rna,
  d.notes,
  array_remove(array_agg(d.fusion_name order by d.pos nulls last, d.fusion_name), null) as fusion_names,
  array_remove(array_agg(distinct d.fluor_name order by d.fluor_name), null) as fluor_names,
  array_remove(array_agg(distinct d.tag_name   order by d.tag_name),   null) as tag_names
from dedup d
group by
  d.plasmid_code, d.plasmid_name, d.nickname, d.resistance, d.supports_invitro_rna, d.notes;

COMMIT;
