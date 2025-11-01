DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='clutch_seq') THEN
    EXECUTE 'ALTER TABLE public.clutch_instances ADD COLUMN clutch_seq smallint';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='expected_genotype_pretty') THEN
    EXECUTE 'ALTER TABLE public.clutch_instances ADD COLUMN expected_genotype_pretty text';
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='clutch_instances' AND column_name='observed_genotype_pretty') THEN
    EXECUTE 'ALTER TABLE public.clutch_instances ADD COLUMN observed_genotype_pretty text';
  END IF;

  IF EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.clutch_instances'::regclass AND conname='uq_clutch_per_cross') THEN
    EXECUTE 'ALTER TABLE public.clutch_instances DROP CONSTRAINT uq_clutch_per_cross';
  END IF;

  IF NOT EXISTS (SELECT 1 FROM pg_constraint WHERE conrelid='public.clutch_instances'::regclass AND conname='uq_clutch_per_cross_seq') THEN
    EXECUTE 'ALTER TABLE public.clutch_instances ADD CONSTRAINT uq_clutch_per_cross_seq UNIQUE (cross_instance_id, clutch_seq)';
  END IF;
END
$$;

CREATE OR REPLACE FUNCTION public.next_clutch_seq(p_cross_id uuid)
RETURNS smallint
LANGUAGE plpgsql
AS $$
DECLARE
  v smallint;
  k bigint;
BEGIN
  SELECT ('x'||substr(encode(p_cross_id::bytea,'hex'),1,16))::bit(64)::bigint INTO k;
  PERFORM pg_advisory_xact_lock(k);
  SELECT COALESCE(MAX(clutch_seq),0)+1 INTO v FROM public.clutch_instances WHERE cross_instance_id=p_cross_id;
  RETURN v;
END
$$;

CREATE OR REPLACE FUNCTION public.trg_clutches_set_seq_and_code()
RETURNS trigger
LANGUAGE plpgsql
AS $$
DECLARE
  v_code text;
BEGIN
  IF NEW.clutch_seq IS NULL THEN
    NEW.clutch_seq := public.next_clutch_seq(NEW.cross_instance_id);
  END IF;

  IF NEW.clutch_instance_code IS NULL THEN
    SELECT cross_run_code INTO v_code FROM public.cross_instances WHERE id=NEW.cross_instance_id;
    IF v_code IS NULL THEN
      RAISE EXCEPTION 'linked cross not found or cross_run_code missing';
    END IF;
    NEW.clutch_instance_code := format('%s-C%s', v_code, lpad(NEW.clutch_seq::text, 2, '0'));
  END IF;

  RETURN NEW;
END
$$;

DROP TRIGGER IF EXISTS trg_clutches_set_seq_and_code ON public.clutch_instances;
CREATE TRIGGER trg_clutches_set_seq_and_code
BEFORE INSERT ON public.clutch_instances
FOR EACH ROW
EXECUTE FUNCTION public.trg_clutches_set_seq_and_code();
