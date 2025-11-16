BEGIN;

-- Drop FT legacy stack in a dependency-safe, idempotent order
DROP TABLE IF EXISTS public.join_fish_treatments_fluorescent CASCADE;
DROP TABLE IF EXISTS public.join_ft_dyes CASCADE;
DROP TABLE IF EXISTS public.join_ft_fusions CASCADE;
DROP TABLE IF EXISTS public.treatments_fluorescent CASCADE;

COMMIT;
