BEGIN;

-- enum we use for container.status
DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='container_status') THEN
    CREATE TYPE container_status AS ENUM ('planned','active','to_kill','retired');
  END IF;
END$$;

-- fish↔tank memberships (idempotent)
CREATE TABLE IF NOT EXISTS public.fish_tank_memberships (
    id uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    fish_id uuid NOT NULL REFERENCES public.fish (id) ON DELETE CASCADE,
    container_id uuid NOT NULL REFERENCES public.containers (id_uuid) ON DELETE RESTRICT,
    joined_at timestamptz NOT NULL DEFAULT now(),
    left_at timestamptz NULL,
    note text NULL
);
CREATE INDEX IF NOT EXISTS idx_ftm_fish ON public.fish_tank_memberships (fish_id);
CREATE INDEX IF NOT EXISTS idx_ftm_container ON public.fish_tank_memberships (container_id);
CREATE UNIQUE INDEX IF NOT EXISTS uq_ftm_fish_open ON public.fish_tank_memberships (fish_id) WHERE left_at IS NULL;

-- status transition helpers (idempotent)
CREATE OR REPLACE FUNCTION public.mark_container_active(p_id uuid, p_by text)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  UPDATE public.containers
  SET status='active',
      status_changed_at=now(),
      activated_at=COALESCE(activated_at, now())
  WHERE id_uuid=p_id;
END$$;

CREATE OR REPLACE FUNCTION public.mark_container_to_kill(p_id uuid, p_by text, p_reason text DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  UPDATE public.containers
  SET status='to_kill',
      status_changed_at=now(),
      deactivated_at=COALESCE(deactivated_at, now()),
      note = CASE WHEN p_reason IS NOT NULL AND p_reason <> '' THEN COALESCE(note,'') || CASE WHEN note IS NULL OR note='' THEN '' ELSE E'\n' END || ('to_kill @ '||now()||' by '||COALESCE(p_by,'?')||COALESCE(' — '||p_reason,'')) ELSE note END
  WHERE id_uuid=p_id;
END$$;

CREATE OR REPLACE FUNCTION public.mark_container_retired(p_id uuid, p_by text, p_reason text DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$
BEGIN
  UPDATE public.containers
  SET status='retired',
      status_changed_at=now(),
      deactivated_at=COALESCE(deactivated_at, now()),
      note = CASE WHEN p_reason IS NOT NULL AND p_reason <> '' THEN COALESCE(note,'') || CASE WHEN note IS NULL OR note='' THEN '' ELSE E'\n' END || ('retired @ '||now()||' by '||COALESCE(p_by,'?')||COALESCE(' — '||p_reason,'')) ELSE note END
  WHERE id_uuid=p_id;
END$$;

-- ensure/create an inventory tank by label; prefer 'active'
CREATE OR REPLACE FUNCTION public.ensure_inventory_tank(
    p_label text, p_by text, p_status container_status DEFAULT 'active'
)
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

-- assign fish → tank (close prior open membership, mark active)
CREATE OR REPLACE FUNCTION public.assign_fish_to_tank(
    p_fish_id uuid, p_container_id uuid, p_by text, p_note text DEFAULT NULL
)
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
