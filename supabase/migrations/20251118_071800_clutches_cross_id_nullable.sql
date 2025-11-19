BEGIN;

ALTER TABLE public.clutches
    ALTER COLUMN cross_id DROP NOT NULL;

COMMIT;
