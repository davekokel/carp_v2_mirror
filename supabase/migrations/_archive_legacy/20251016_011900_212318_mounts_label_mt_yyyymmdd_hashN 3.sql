begin;

-- 0) Ensure mount_label column exists
do $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM information_schema.columns  WHERE table_schema='public' AND table_name='mounts' AND column_name='mount_label'
  ) THEN
    ALTER TABLE public.mounts ADD COLUMN mount_label text;
  END IF;
END$$;

-- 1) Day-global label backfill: MT-YYYY-MM-DD #N across ALL runs
with ranked as (
    select
        m.id,
        to_char(m.mount_date, 'YYYY-MM-DD') as dlabel,
        row_number() over (
            partition by m.mount_date
            order by coalesce(m.time_mounted, m.mount_date::timestamptz, m.created_at) nulls last, m.id
        ) as rn
    from public.mounts AS m
    where m.mount_label is NULL or btrim(m.mount_label) = ''
)

update public.mounts t
set mount_label = 'MT-' || r.dlabel || ' #' || r.rn::text
from ranked AS r
where t.id = r.id;

commit;

begin;

-- 2) Uniqueness: day-global label must be unique across all mounts
do $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_constraint  WHERE conrelid='public.mounts'::regclass AND conname='uq_mounts_run_date_label'
  ) THEN
    ALTER TABLE public.mounts DROP CONSTRAINT uq_mounts_run_date_label;
  END IF;
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint  WHERE conrelid='public.mounts'::regclass AND conname='uq_mounts_label'
  ) THEN
    ALTER TABLE public.mounts ADD CONSTRAINT uq_mounts_label UNIQUE (mount_label);
  END IF;
END$$;

alter table public.mounts
alter column mount_label set not null;

-- 3) Per-day label sequencer
create table if not exists public.mount_label_seq_day (
    mount_date date primary key,
    last integer not null
);

-- Seed to current counts per day (safe if rerun)
insert into public.mount_label_seq_day (mount_date, last)
select
    m.mount_date,
    count(*)::int
from public.mounts AS m
group by m.mount_date
on conflict (mount_date) do update set last = excluded.last;

-- 4) Trigger: keep mount_code machine-friendly, set mount_label as MT-YYYY-MM-DD #N (day-global)
create or replace function public.trg_mounts_alloc_seq()
returns trigger
language plpgsql
as $$
DECLARE
  v_next int;
  v_run  text;
BEGIN
  -- Per-run seq for mount_code (unchanged)
  IF NEW.seq IS NULL OR NEW.seq = 0 THEN
    INSERT INTO public.mount_seq(cross_instance_id, last)
    VALUES (NEW.cross_instance_id, 0)
    ON CONFLICT (cross_instance_id) DO UPDATE
      SET last = public.mount_seq.last + 1
    RETURNING last INTO v_next;
    NEW.seq := v_next::smallint;
  END IF;

  -- Machine code: MT-<run>-NN
  SELECT cross_run_code INTO v_run FROM public.cross_instances  WHERE id = NEW.cross_instance_id;
  NEW.mount_code := 'MT-' || v_run || '-' || lpad(NEW.seq::text, 2, '0');

  -- Day-global label: MT-YYYY-MM-DD #N
  INSERT INTO public.mount_label_seq_day(mount_date, last)
  VALUES (NEW.mount_date, 1)
  ON CONFLICT (mount_date) DO UPDATE
    SET last = public.mount_label_seq_day.last + 1
  RETURNING last INTO v_next;

  NEW.mount_label := 'MT-' || to_char(NEW.mount_date, 'YYYY-MM-DD') || ' #' || v_next::text;

  RETURN NEW;
END
$$;

drop trigger if exists mounts_alloc_seq on public.mounts;
create trigger mounts_alloc_seq
before insert on public.mounts
for each row
execute function public.trg_mounts_alloc_seq();

commit;
