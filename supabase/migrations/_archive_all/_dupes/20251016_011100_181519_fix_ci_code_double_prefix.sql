begin;

-- 1) Replace trigger function to avoid double "XR-"
create or replace function public.trg_clutch_instances_alloc_seq()
returns trigger
language plpgsql
as $$
DECLARE
  v_next int;
  v_run text;
BEGIN
  IF NEW.seq IS NULL OR NEW.seq = 0 THEN
    INSERT INTO public.clutch_instance_seq(cross_instance_id, last)
    VALUES (NEW.cross_instance_id, 0)
    ON CONFLICT (cross_instance_id) DO UPDATE
      SET last = public.clutch_instance_seq.last + 1
    RETURNING last INTO v_next;

    NEW.seq := v_next::smallint;
  END IF;

  -- v_run already looks like "XR-2510001"; do NOT add another "XR-"
  SELECT cross_run_code INTO v_run
  FROM public.cross_instances  WHERE id = NEW.cross_instance_id;

  NEW.clutch_instance_code := v_run || '-' || lpad(NEW.seq::text, 2, '0');
  RETURN NEW;
END
$$;

-- Ensure trigger is present and points at the latest function
drop trigger if exists clutch_instances_alloc_seq on public.clutch_instances;
create trigger clutch_instances_alloc_seq
before insert on public.clutch_instances
for each row
execute function public.trg_clutch_instances_alloc_seq();

-- 2) Backfill existing rows with "XR-XR..." → strip the first "XR-"
update public.clutch_instances
set clutch_instance_code = substring(clutch_instance_code from 4)
where clutch_instance_code like 'XR-XR%';

commit;
