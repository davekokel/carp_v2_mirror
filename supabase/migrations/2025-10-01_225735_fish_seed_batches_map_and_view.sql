-- 1) Deterministic mapping: one seed_batch_id per fish_id
create table if not exists public.fish_seed_batches (
  fish_id       uuid primary key references public.fish(id_uuid) on delete cascade,
  seed_batch_id text not null,
  updated_at    timestamptz default now()
);

-- 2) Backfill from logs (latest per fish)
insert into public.fish_seed_batches (fish_id, seed_batch_id)
select distinct on (llf.fish_id)
  llf.fish_id,
  llf.seed_batch_id
from public.load_log_fish llf
where llf.seed_batch_id is not null
order by llf.fish_id, llf.logged_at desc
on conflict (fish_id) do update
  set seed_batch_id = excluded.seed_batch_id,
      updated_at    = now();

-- 3) Labeled overview: join via fish_code -> fish -> fish_seed_batches,
--    then optional pretty label via public.seed_batches if present.
create or replace view public.vw_fish_overview_with_label as
with seed_map as (
  select
    trim(f.fish_code) as fish_code_norm,
    fsb.seed_batch_id
  from public.fish f
  join public.fish_seed_batches fsb
    on fsb.fish_id = f.id_uuid
),
label_map as (
  select
    seed_batch_id,
    nullif(trim(batch_label), '') as batch_label
  from public.seed_batches
)
select
  v.*,
  coalesce(lm.batch_label, sm.seed_batch_id) as batch_label
from public.vw_fish_overview v
left join seed_map sm
  on trim(v.fish_code) = sm.fish_code_norm
left join label_map lm
  using (seed_batch_id);
