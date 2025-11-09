BEGIN;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plasmids' AND column_name='nickname') THEN
    ALTER TABLE public.plasmids ADD COLUMN nickname text;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plasmids' AND column_name='resistance') THEN
    ALTER TABLE public.plasmids ADD COLUMN resistance text;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='plasmids' AND column_name='notes') THEN
    ALTER TABLE public.plasmids ADD COLUMN notes text;
  END IF;
END $$;
DO $$ BEGIN
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='rnas' AND column_name='nickname') THEN
    ALTER TABLE public.rnas ADD COLUMN nickname text;
  END IF;
  IF NOT EXISTS (SELECT 1 FROM information_schema.columns WHERE table_schema='public' AND table_name='rnas' AND column_name='notes') THEN
    ALTER TABLE public.rnas ADD COLUMN notes text;
  END IF;
END $$;
COMMIT;
