begin;

create extension if not exists pgcrypto;

-- Canonical mounts table
create table if not exists public.bruker_mounts (
  id                 uuid primary key default gen_random_uuid(),
  clutch_instance_id uuid references public.clutch_instances(id) on delete set null,
  sample_id          text,                    -- optional: your lab sample id / selection id
  mount_code         text unique,             -- human code e.g., MT-YYYYMMDD-n
  mounting_orientation text,                  -- e.g., "Dorsal, Head user"
  n_top              int,
  n_bottom           int,
  operator           text,
  instrument         text,
  time_mounted       timestamptz default now(),
  imaged_at          timestamptz,             -- optional imaging time
  notes              text,
  created_by         text,
  created_at         timestamptz default now()
);
create index if not exists bm_time_idx   on public.bruker_mounts (time_mounted desc);
create index if not exists bm_ci_idx     on public.bruker_mounts (clutch_instance_id);

-- Simple read view consumed by the Overview Mounts page
create or replace view public.v_overview_mounts as
select
  id                    as mount_id,
  mount_code,
  clutch_instance_id,
  sample_id,
  mounting_orientation,
  n_top,
  n_bottom,
  operator,
  instrument,
  time_mounted         as mounted_at,
  imaged_at,
  notes,
  created_by,
  created_at
from public.bruker_mounts;

comment on view public.v_overview_mounts is 'Readable projection of bruker_mounts for UI pages.';

commit;
