begin;

-- 0) Columns (nullable during backfill)
do $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='seq'
  ) THEN
    ALTER TABLE public.clutch_instances ADD COLUMN seq smallint;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='clutch_instance_code'
  ) THEN
    ALTER TABLE public.clutch_instances ADD COLUMN clutch_instance_code text;
  END IF;
END$$;

-- 1) Per-run sequencer table
create table if not exists public.clutch_instance_seq (
    cross_instance_id uuid primary key,
    last integer not null
);

-- 2) Backfill existing rows (deterministic by created_at then id)
with ranked as (
    select
        ci.id,
        ci.cross_instance_id,
        row_number() over (
            partition by ci.cross_instance_id
            order by ci.created_at nulls last, ci.id
        )::smallint as rn
    from public.clutch_instances AS ci
    where ci.seq is NULL
)

update public.clutch_instances x
set seq = r.rn
from ranked AS r
where x.id = r.id;

-- 2b) Backfill codes from seq AS and cross_run_code
with src as (
    select
        ci.id,
        ci.seq,
        cinst.cross_run_code
    from public.clutch_instances AS ci
    inner join public.cross_instances AS cinst on ci.cross_instance_id = cinst.id
    where ci.clutch_instance_code is NULL
)

update public.clutch_instances t
set clutch_instance_code = 'XR-' || s.cross_run_code || '-' || lpad(s.seq::text, 2, '0')
from src AS s
where t.id = s.id;

-- 2c) Seed the sequencer table to current max per run
insert into public.clutch_instance_seq (cross_instance_id, last)
select
    ci.cross_instance_id,
    max(ci.seq)::int
from public.clutch_instances AS ci
group by ci.cross_instance_id
on conflict (cross_instance_id) do update set last = excluded.last;

-- 3) Constraints + indexes
do $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint  WHERE conrelid='public.clutch_instances'::regclass
      AND conname='uq_clutch_instances_run_seq'
  ) THEN
    ALTER TABLE public.clutch_instances
      ADD CONSTRAINT uq_clutch_instances_run_seq UNIQUE (cross_instance_id, seq);
  END IF;
END$$;

do $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint  WHERE conrelid='public.clutch_instances'::regclass
      AND conname='uq_clutch_instances_code'
  ) THEN
    ALTER TABLE public.clutch_instances
      ADD CONSTRAINT uq_clutch_instances_code UNIQUE (clutch_instance_code);
  END IF;
END$$;

alter table public.clutch_instances
alter column seq set not null,
alter column clutch_instance_code set not null;

create index if not exists ix_clutch_instances_code on public.clutch_instances (clutch_instance_code);

-- 4) Trigger to allocate next seq per run and set code
create or replace function public.trg_clutch_instances_alloc_seq()
returns trigger
language plpgsql
as $$
DECLARE
  v_last int;
  v_next int;
  v_run text;
BEGIN
  -- Only compute if missing
  IF NEW.seq IS NULL OR NEW.seq = 0 THEN
    -- upsert per-run counter atomically
    INSERT INTO public.clutch_instance_seq(cross_instance_id, last)
    VALUES (NEW.cross_instance_id, 0)
    ON CONFLICT (cross_instance_id) DO UPDATE
      SET last = public.clutch_instance_seq.last + 1
    RETURNING last INTO v_last;

    v_next := v_last;          -- last already incremented by +1
    NEW.seq := v_next::smallint;
  END IF;

  -- Build code XR-<run>-NN
  SELECT cross_run_code INTO v_run FROM public.cross_instances  WHERE id = NEW.cross_instance_id;
  NEW.clutch_instance_code := 'XR-' || v_run || '-' || lpad(NEW.seq::text, 2, '0');

  RETURN NEW;
END
$$;

drop trigger if exists clutch_instances_alloc_seq on public.clutch_instances;
create trigger clutch_instances_alloc_seq
before insert on public.clutch_instances
for each row
execute function public.trg_clutch_instances_alloc_seq();

commit;
