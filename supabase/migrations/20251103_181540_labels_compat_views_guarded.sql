BEGIN;

-- If these are tables, rename them to *_legacy (idempotent)
DO $$
BEGIN
  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='tank_label_history' AND c.relkind='r'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='tank_label_history_legacy'
  ) THEN
    EXECUTE 'ALTER TABLE public.tank_label_history RENAME TO tank_label_history_legacy';
  END IF;

  IF EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='cross_label_history' AND c.relkind='r'
  ) AND NOT EXISTS (
    SELECT 1 FROM pg_class c
    JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='public' AND c.relname='cross_label_history_legacy'
  ) THEN
    EXECUTE 'ALTER TABLE public.cross_label_history RENAME TO cross_label_history_legacy';
  END IF;
END$$;

-- Now (re)create views with the original names
DROP VIEW IF EXISTS public.tank_label_history;
CREATE VIEW public.tank_label_history AS
SELECT
  gen_random_uuid() AS id,
  v.tank_id        AS tank_uuid,
  v.label_text     AS label,
  v.created_at     AS created_at,
  NULL::text       AS created_by
FROM public.v_labels_for_tanks v;

DROP VIEW IF EXISTS public.cross_label_history;
CREATE VIEW public.cross_label_history AS
SELECT
  gen_random_uuid() AS id,
  v.cross_id        AS cross_id,
  v.label_text      AS label,
  v.created_at      AS created_at,
  NULL::text        AS created_by
FROM public.v_labels_for_crosses v;

-- Optional: drop legacy/defunct tables if present (guarded)
DO $$
BEGIN
  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='clutches_legacy')
  THEN EXECUTE 'DROP TABLE public.clutches_legacy'; END IF;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='tank_label_history_legacy')
  THEN EXECUTE 'DROP TABLE public.tank_label_history_legacy'; END IF;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='cross_label_history_legacy')
  THEN EXECUTE 'DROP TABLE public.cross_label_history_legacy'; END IF;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='fish_tank_memberships_legacy')
  THEN EXECUTE 'DROP TABLE public.fish_tank_memberships_legacy'; END IF;

  IF EXISTS (SELECT 1 FROM information_schema.tables WHERE table_schema='public' AND table_name='tank_history')
  THEN EXECUTE 'DROP TABLE public.tank_history'; END IF;
END$$;

COMMIT;
