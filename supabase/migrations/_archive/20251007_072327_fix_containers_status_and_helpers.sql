BEGIN;
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='container_status') THEN
    CREATE TYPE container_status AS ENUM ('planned','active','inactive','retired','unknown');
  END IF;
END$$;
DO $$
DECLARE
  is_enum boolean;
BEGIN
  SELECT atttypid::regtype::text='container_status'
  INTO is_enum
  FROM pg_attribute
  WHERE attrelid='public.containers'::regclass AND attname='status' AND NOT attisdropped;

  IF NOT is_enum THEN
    ALTER TABLE public.containers ALTER COLUMN status DROP DEFAULT;
    ALTER TABLE public.containers
      ALTER COLUMN status TYPE container_status USING
        CASE
          WHEN status::text IN ('planned','active','inactive','retired','unknown') THEN status::container_status
          ELSE 'unknown'::container_status
        END;
    ALTER TABLE public.containers ALTER COLUMN status SET DEFAULT 'planned'::container_status;
  END IF;
END$$;

CREATE TABLE IF NOT EXISTS public.fish_tank_memberships (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  fish_id       uuid NOT NULL REFERENCES public.fish(id) ON DELETE CASCADE,
  container_id  uuid NOT NULL REFERENCES public.containers(id_uuid) ON DELETE RESTRICT,
  joined_at     timestamptz NOT NULL DEFAULT now(),
  left_at       timestamptz NULL,
  note          text NULL
);

CREATE INDEX IF NOT EXISTS idx_ftm_fish ON public.fish_tank_memberships(fish_id);
CREATE INDEX IF NOT EXISTS idx_ftm_container ON public.fish_tank_memberships(container_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ftm_fish_open
  ON public.fish_tank_memberships(fish_id) WHERE left_at IS NULL;

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

CREATE OR REPLACE FUNCTION public.ensure_inventory_tank(p_label text, p_by text, p_status container_status DEFAULT 'active')
RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
  rid uuid;
BEGIN
  SELECT id_uuid INTO rid
  FROM public.containers
  WHERE container_type='inventory_tank' AND COALESCE(label,'') = COALESCE(p_label,'')
  ORDER BY created_at ASC
  LIMIT 1;

  IF rid IS NULL THEN
    INSERT INTO public.containers (container_type, label, status, created_by, note)
    VALUES ('inventory_tank', p_label, COALESCE(p_status,'active'), p_by, NULL)
    RETURNING id_uuid INTO rid;
  ELSE
    IF p_status='active' THEN
      PERFORM public.mark_container_active(rid, p_by);
    END IF;
  END IF;

  RETURN rid;
END$$;

CREATE OR REPLACE FUNCTION public.assign_fish_to_tank(p_fish_id uuid, p_container_id uuid, p_by text, p_note text DEFAULT NULL)
RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
  rid uuid;
BEGIN
  UPDATE public.fish_tank_memberships
  SET left_at = now()
  WHERE fish_id = p_fish_id AND left_at IS NULL;

  INSERT INTO public.fish_tank_memberships (fish_id, container_id, note)
  VALUES (p_fish_id, p_container_id, p_note)
  RETURNING id INTO rid;

  PERFORM public.mark_container_active(p_container_id, p_by);
  RETURN rid;
END$$;

COMMIT;
