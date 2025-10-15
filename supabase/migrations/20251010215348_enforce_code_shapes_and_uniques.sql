-- Idempotent guards for code shapes + uniques (NOT VALID + best-effort VALIDATE)

-- fish.fish_code
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_fish_code' AND conrelid = 'public.fish'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD CONSTRAINT uq_fish_code UNIQUE (fish_code)';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_fish_code_shape' AND conrelid = 'public.fish'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.fish ADD CONSTRAINT chk_fish_code_shape CHECK (fish_code IS NULL OR fish_code ~ ''^FSH-[0-9A-Z]{2}[0-9A-Z]+$'') NOT VALID';
    BEGIN
      EXECUTE 'ALTER TABLE public.fish VALIDATE CONSTRAINT chk_fish_code_shape';
    EXCEPTION WHEN others THEN
      -- leave it NOT VALID; blocks new bad rows, lets us clean existing later
      NULL;
    END;
  END IF;
END
$$ LANGUAGE plpgsql;

-- containers.tank_code
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_tank_code' AND conrelid = 'public.containers'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.containers ADD CONSTRAINT uq_tank_code UNIQUE (tank_code)';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_tank_code_shape' AND conrelid = 'public.containers'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.containers ADD CONSTRAINT chk_tank_code_shape CHECK (tank_code IS NULL OR tank_code ~ ''^TANK-[0-9A-Z]{2}[0-9A-Z]{4,}$'') NOT VALID';
    BEGIN
      EXECUTE 'ALTER TABLE public.containers VALIDATE CONSTRAINT chk_tank_code_shape';
    EXCEPTION WHEN others THEN
      NULL;
    END;
  END IF;
END
$$ LANGUAGE plpgsql;

-- crosses.cross_code
DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'uq_cross_code' AND conrelid = 'public.crosses'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.crosses ADD CONSTRAINT uq_cross_code UNIQUE (cross_code)';
  END IF;

  IF NOT EXISTS (
    SELECT 1 FROM pg_constraint
    WHERE conname = 'chk_cross_code_shape' AND conrelid = 'public.crosses'::regclass
  ) THEN
    EXECUTE 'ALTER TABLE public.crosses ADD CONSTRAINT chk_cross_code_shape CHECK (cross_code IS NULL OR cross_code ~ ''^CROSS-[0-9A-Z]{2}[0-9A-Z]{4,}$'') NOT VALID';
    BEGIN
      EXECUTE 'ALTER TABLE public.crosses VALIDATE CONSTRAINT chk_cross_code_shape';
    EXCEPTION WHEN others THEN
      NULL;
    END;
  END IF;
END
$$ LANGUAGE plpgsql;
