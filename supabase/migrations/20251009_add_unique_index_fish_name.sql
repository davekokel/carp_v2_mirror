BEGIN;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fish_name ON public.fish(name);

COMMIT;
