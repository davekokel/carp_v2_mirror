BEGIN;

DO $$
BEGIN
  IF NOT EXISTS (SELECT 1 FROM pg_type WHERE typname='container_status') THEN
    CREATE TYPE container_status AS ENUM ('planned','active','to_kill','retired');
  END IF;
END$$;

ALTER TABLE public.containers
  ADD COLUMN IF NOT EXISTS status_changed_at timestamptz NOT NULL DEFAULT now(),
  ADD COLUMN IF NOT EXISTS activated_at timestamptz NULL,
  ADD COLUMN IF NOT EXISTS deactivated_at timestamptz NULL,
  ADD COLUMN IF NOT EXISTS last_seen_at timestamptz NULL,
  ADD COLUMN IF NOT EXISTS last_seen_source text NULL;

CREATE TABLE IF NOT EXISTS public.container_status_history (
  id            uuid PRIMARY KEY DEFAULT gen_random_uuid(),
  container_id  uuid NOT NULL REFERENCES public.containers(id_uuid) ON DELETE CASCADE,
  old_status    container_status NOT NULL,
  new_status    container_status NOT NULL,
  changed_at    timestamptz NOT NULL DEFAULT now(),
  changed_by    text NULL,
  reason        text NULL
);

CREATE INDEX IF NOT EXISTS idx_csh_container ON public.container_status_history(container_id);
CREATE INDEX IF NOT EXISTS idx_csh_changed_at ON public.container_status_history(changed_at);

CREATE OR REPLACE FUNCTION public.set_container_status(
  p_id uuid,
  p_new container_status,
  p_by text,
  p_reason text DEFAULT NULL
) RETURNS void LANGUAGE plpgsql AS $$
DECLARE
  v_old container_status;
  v_allowed boolean := false;
BEGIN
  SELECT status INTO v_old FROM public.containers WHERE id_uuid = p_id FOR UPDATE;
  IF v_old IS NULL THEN RAISE EXCEPTION 'container % not found', p_id; END IF;
  IF v_old = p_new THEN
    UPDATE public.containers SET status_changed_at = now() WHERE id_uuid = p_id;
    RETURN;
  END IF;
  v_allowed :=
       (v_old = 'planned' AND p_new IN ('active','retired'))
    OR (v_old = 'active'  AND p_new IN ('to_kill','retired'))
    OR (v_old = 'to_kill' AND p_new IN ('retired'))
    OR (v_old = 'retired' AND p_new IN ('retired'));
  IF NOT v_allowed THEN RAISE EXCEPTION 'illegal status transition: % → %', v_old, p_new; END IF;

  UPDATE public.containers
  SET status = p_new,
      status_changed_at = now(),
      activated_at   = CASE WHEN p_new='active' THEN COALESCE(activated_at, now()) ELSE activated_at END,
      deactivated_at = CASE WHEN p_new IN ('to_kill','retired') THEN COALESCE(deactivated_at, now()) ELSE deactivated_at END,
      note = CASE
               WHEN p_reason IS NOT NULL AND p_reason <> ''
                 THEN COALESCE(note,'') || CASE WHEN note IS NULL OR note='' THEN '' ELSE E'\n' END ||
                      ('status: '||v_old||' → '||p_new||' @ '||now()||' by '||COALESCE(p_by,'?')||COALESCE(' — '||p_reason,''))
               ELSE note
             END
  WHERE id_uuid = p_id;

  INSERT INTO public.container_status_history(container_id, old_status, new_status, changed_by, reason)
  VALUES (p_id, v_old, p_new, p_by, p_reason);
END $$;

CREATE OR REPLACE FUNCTION public.mark_container_active(p_id uuid, p_by text)
RETURNS void LANGUAGE plpgsql AS $$ BEGIN
  PERFORM public.set_container_status(p_id, 'active', p_by, NULL);
END $$;

CREATE OR REPLACE FUNCTION public.mark_container_to_kill(p_id uuid, p_by text, p_reason text DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$ BEGIN
  PERFORM public.set_container_status(p_id, 'to_kill', p_by, p_reason);
END $$;

CREATE OR REPLACE FUNCTION public.mark_container_retired(p_id uuid, p_by text, p_reason text DEFAULT NULL)
RETURNS void LANGUAGE plpgsql AS $$ BEGIN
  PERFORM public.set_container_status(p_id, 'retired', p_by, p_reason);
END $$;

CREATE OR REPLACE FUNCTION public.mark_container_inactive(p_id uuid, p_by text)
RETURNS void LANGUAGE plpgsql AS $$ BEGIN
  PERFORM public.set_container_status(p_id, 'to_kill', p_by, 'compat: inactive→to_kill');
END $$;

CREATE OR REPLACE FUNCTION public.trg_log_container_status()
RETURNS trigger LANGUAGE plpgsql AS $$
BEGIN
  IF TG_OP = 'UPDATE' AND NEW.status IS DISTINCT FROM OLD.status THEN
    INSERT INTO public.container_status_history(container_id, old_status, new_status, changed_by, reason)
    VALUES (NEW.id_uuid, OLD.status, NEW.status, current_user, 'trigger');
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_containers_status_history ON public.containers;
CREATE TRIGGER trg_containers_status_history
AFTER UPDATE OF status ON public.containers
FOR EACH ROW EXECUTE FUNCTION public.trg_log_container_status();

COMMIT;
