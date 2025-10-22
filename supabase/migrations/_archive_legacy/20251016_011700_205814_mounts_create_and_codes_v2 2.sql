-- =========================
-- Phase A: create table + columns + backfill
-- =========================
begin;

-- 0) Base table
create table if not exists public.mounts (
    id uuid primary key default gen_random_uuid(),
    cross_instance_id uuid not null references public.cross_instances (id) on delete cascade,
    mount_date date not null,
    sample_id text not null,
    mount_type text,
    notes text,
    created_at timestamptz default now(),
    created_by text
);

-- 1) Columns (nullable during backfill)
do $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='time_mounted') THEN
    ALTER TABLE public.mounts ADD COLUMN time_mounted timestamptz;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='mounting_orientation') THEN
    ALTER TABLE public.mounts ADD COLUMN mounting_orientation text;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='n_top') THEN
    ALTER TABLE public.mounts ADD COLUMN n_top integer DEFAULT 0;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='n_bottom') THEN
    ALTER TABLE public.mounts ADD COLUMN n_bottom integer DEFAULT 0;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='seq') THEN
    ALTER TABLE public.mounts ADD COLUMN seq smallint;
  END IF;

  IF NOT EXISTS (SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='mount_code') THEN
    ALTER TABLE public.mounts ADD COLUMN mount_code text;
  END IF;
END$$;

-- 2) Non-negative checks (use DO-blocks to avoid IF NOT EXISTS syntax)
do $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint  WHERE conname='ck_mounts_n_top_nonneg' AND conrelid='public.mounts'::regclass
  ) THEN
    ALTER TABLE public.mounts
      ADD CONSTRAINT ck_mounts_n_top_nonneg CHECK (n_top IS NULL OR n_top >= 0);
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint  WHERE conname='ck_mounts_n_bottom_nonneg' AND conrelid='public.mounts'::regclass
  ) THEN
    ALTER TABLE public.mounts
      ADD CONSTRAINT ck_mounts_n_bottom_nonneg CHECK (n_bottom IS NULL OR n_bottom >= 0);
  END IF;
END$$;

-- 3) Per-run sequencer table
create table if not exists public.mount_seq (
    cross_instance_id uuid primary key,
    last integer not null
);

-- 4) Backfill seq deterministically (oldest first)
with ranked as (
    select
        m.id,
        m.cross_instance_id,
        row_number() over (
            partition by m.cross_instance_id
            order by coalesce(m.time_mounted, m.mount_date::timestamptz, m.created_at) nulls last, m.id
        )::smallint as rn
    from public.mounts AS m
    where m.seq is NULL
)

update public.mounts t
set seq = r.rn
from ranked AS r
where t.id = r.id;

-- 5) Backfill mount_code: MT-<run>-NN
with src as (
    select
        m.id,
        m.seq,
        ci.cross_run_code as run_code
    from public.mounts AS m
    inner join public.cross_instances AS ci on m.cross_instance_id = ci.id
    where (m.mount_code is NULL or btrim(m.mount_code) = '')
)

update public.mounts t
set mount_code = 'MT-' || s.run_code || '-' || lpad(s.seq::text, 2, '0')
from src AS s
where t.id = s.id;

-- 6) Seed sequencer to current max per run
insert into public.mount_seq (cross_instance_id, last)
select
    m.cross_instance_id,
    max(m.seq)::int
from public.mounts AS m
group by m.cross_instance_id
on conflict (cross_instance_id) do update set last = excluded.last;

commit;

-- =========================
-- Phase B: constraints + indexes + trigger
-- =========================
begin;

-- Uniques
do $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_constraint  WHERE conrelid='public.mounts'::regclass AND conname='uq_mounts_run_seq') THEN
    ALTER TABLE public.mounts
      ADD CONSTRAINT uq_mounts_run_seq UNIQUE (cross_instance_id, seq);
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint  WHERE conrelid='public.mounts'::regclass AND conname='uq_mounts_code') THEN
    ALTER TABLE public.mounts
      ADD CONSTRAINT uq_mounts_code UNIQUE (mount_code);
  END IF;
END$$;

-- Not nulls after backfill
alter table public.mounts
alter column seq set not null,
alter column mount_code set not null;

-- Indexes
create index if not exists ix_mounts_cross_instance_id on public.mounts (cross_instance_id);
create index if not exists ix_mounts_mount_date on public.mounts (mount_date desc);
create index if not exists ix_mounts_time_mounted on public.mounts (time_mounted desc);
create index if not exists ix_mounts_code on public.mounts (mount_code);

-- Trigger to allocate per-run seq and code MT-<run>-NN on INSERT
create or replace function public.trg_mounts_alloc_seq()
returns trigger
language plpgsql
as $$
DECLARE
  v_next int;
  v_run  text;
BEGIN
  IF NEW.seq IS NULL OR NEW.seq = 0 THEN
    INSERT INTO public.mount_seq(cross_instance_id, last)
    VALUES (NEW.cross_instance_id, 0)
    ON CONFLICT (cross_instance_id) DO UPDATE
      SET last = public.mount_seq.last + 1
    RETURNING last INTO v_next;

    NEW.seq := v_next::smallint;
  END IF;

  SELECT cross_run_code INTO v_run FROM public.cross_instances  WHERE id = NEW.cross_instance_id;
  NEW.mount_code := 'MT-' || v_run || '-' || lpad(NEW.seq::text, 2, '0');
  RETURN NEW;
END
$$;

drop trigger if exists mounts_alloc_seq on public.mounts;
create trigger mounts_alloc_seq
before insert on public.mounts
for each row
execute function public.trg_mounts_alloc_seq();

commit;
