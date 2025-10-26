begin;

create or replace function public.gen_tank_pair_code()
returns trigger
language plpgsql
as $$
declare
  _next int;
begin
  if coalesce(new.fish_pair_code,'') = '' then
    raise exception 'fish_pair_code is required to generate tank_pair_code';
  end if;

  if coalesce(new.tank_pair_code,'') <> '' then
    return new;
  end if;

  select coalesce(max((regexp_match(tank_pair_code, '-(\d+)$'))[1]::int), 0) + 1
    into _next
  from public.tank_pairs
  where tank_pair_code like format('TP(%s)-%%', new.fish_pair_code);

  new.tank_pair_code := format('TP(%s)-%s', new.fish_pair_code, _next);
  return new;
end$$;

alter table public.tank_pairs
  add column if not exists tank_pair_code text;

create unique index if not exists ux_tank_pairs_tank_pair_code
  on public.tank_pairs(tank_pair_code);

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'chk_fish_pair_code_fmt'
      and conrelid = 'public.tank_pairs'::regclass
  ) then
    execute $$alter table public.tank_pairs
             add constraint chk_fish_pair_code_fmt
             check (fish_pair_code ~ '^FP-[0-9]{5}$') not valid$$;
    execute $$alter table public.tank_pairs
             validate constraint chk_fish_pair_code_fmt$$;
  end if;

  if not exists (
    select 1 from pg_constraint
    where conname = 'chk_tank_pair_code_fmt'
      and conrelid = 'public.tank_pairs'::regclass
  ) then
    execute $$alter table public.tank_pairs
             add constraint chk_tank_pair_code_fmt
             check (tank_pair_code ~ '^TP\\(FP-[0-9]{5}\\)-[1-9][0-9]*$') not valid$$;
    execute $$alter table public.tank_pairs
             validate constraint chk_tank_pair_code_fmt$$;
  end if;
end$$;

drop trigger if exists trg_gen_tank_pair_code on public.tank_pairs;
create trigger trg_gen_tank_pair_code
before insert on public.tank_pairs
for each row
execute function public.gen_tank_pair_code();

create or replace view public.v_tank_pairs as
select
  t.id,
  t.tank_pair_code,
  t.fish_pair_code,
  t.status,
  t.created_by,
  t.created_at,
  t.mother_tank_id,
  t.father_tank_id,
  vtm.fish_code as mom_fish_code,
  vtm.tank_code as mom_tank_code,
  vtf.fish_code as dad_fish_code,
  vtf.tank_code as dad_tank_code,
  coalesce(mv.genotype_text,'') as mom_genotype,
  coalesce(dv.genotype_text,'') as dad_genotype
from public.tank_pairs t
left join public.v_tanks vtm on vtm.tank_uuid = t.mother_tank_id
left join public.v_tanks vtf on vtf.tank_uuid = t.father_tank_id
left join public.v_fish_overview mv on mv.fish_code = vtm.fish_code
left join public.v_fish_overview dv on dv.fish_code = vtf.fish_code;

do $$
begin
  if not exists (
    select 1 from pg_constraint
    where conname = 'chk_ci_tank_pair_code_fmt'
      and conrelid = 'public.cross_instances'::regclass
  ) then
    execute $$alter table public.cross_instances
             add constraint chk_ci_tank_pair_code_fmt
             check (tank_pair_code ~ '^TP\\(FP-[0-9]{5}\\)-[1-9][0-9]*$') not valid$$;
    execute $$alter table public.cross_instances
             validate constraint chk_ci_tank_pair_code_fmt$$;
  end if;
end$$;

create index if not exists ix_tank_pairs_fish_pair_code on public.tank_pairs(fish_pair_code);
create index if not exists ix_ci_tank_pair_code on public.cross_instances(tank_pair_code);

commit;
