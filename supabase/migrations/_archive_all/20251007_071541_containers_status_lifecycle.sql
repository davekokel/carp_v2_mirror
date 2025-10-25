BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='container_status') THEN
    CREATE TYPE container_status AS ENUM ('planned','active','inactive','retired','unknown');
  END IF;
END$$;

ALTER TABLE public.containers
ALTER COLUMN status DROP DEFAULT;
DO $$
BEGIN
  IF (SELECT data_type FROM information_schema.columns WHERE table_schema='public' AND table_name='containers' AND column_name='status') <> 'USER-DEFINED' THEN
    ALTER TABLE public.containers
      ALTER COLUMN status TYPE container_status USING
        CASE
          WHEN status IN ('planned','active','inactive','retired','unknown') THEN status::container_status
          ELSE 'unknown'::container_status
        END;
  END IF;
END$$;

ALTER TABLE public.containers
ALTER COLUMN status SET DEFAULT 'planned';

ALTER TABLE public.containers
ADD COLUMN IF NOT EXISTS status_changed_at timestamptz NOT NULL DEFAULT now(),
ADD COLUMN IF NOT EXISTS activated_at timestamptz NULL,
ADD COLUMN IF NOT EXISTS deactivated_at timestamptz NULL,
ADD COLUMN IF NOT EXISTS last_seen_at timestamptz NULL,
ADD COLUMN IF NOT EXISTS last_seen_source text NULL;

CREATE OR REPLACE FUNCTION public.mark_container_active(p_id uuid, p_by text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  UPDATE public.containers
  SET status='active',
      status_changed_at=now(),
      activated_at=COALESCE(activated_at, now())
  WHERE id_uuid=p_id;
END$$;

CREATE OR REPLACE FUNCTION public.mark_container_inactive(p_id uuid, p_by text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  UPDATE public.containers
  SET status='inactive',
      status_changed_at=now(),
      deactivated_at=COALESCE(deactivated_at, now())
  WHERE id_uuid=p_id;
END$$;

COMMIT;
