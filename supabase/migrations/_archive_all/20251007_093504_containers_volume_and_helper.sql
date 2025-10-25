BEGIN;

ALTER TABLE public.containers
ADD COLUMN IF NOT EXISTS tank_volume_l integer NULL;

ALTER TABLE public.containers
DROP CONSTRAINT IF EXISTS chk_containers_volume_allowed,
ADD CONSTRAINT chk_containers_volume_allowed
CHECK (tank_volume_l IS NULL OR tank_volume_l IN (2, 4, 8, 16));

-- helper that creates (or reuses) an inventory tank with a volume and status
CREATE OR REPLACE FUNCTION public.ensure_inventory_tank_v(
    p_label text,
    p_by text,
    p_status container_status DEFAULT 'active',
    p_volume_l integer DEFAULT NULL
) RETURNS uuid LANGUAGE plpgsql AS $$
DECLARE
  rid uuid;
BEGIN
  SELECT id_uuid INTO rid
  FROM public.containers
  WHERE container_type='inventory_tank'
    AND COALESCE(label,'') = COALESCE(p_label,'')
  ORDER BY created_at ASC
  LIMIT 1;

  IF rid IS NULL THEN
    INSERT INTO public.containers (container_type, label, status, created_by, tank_volume_l, note)
    VALUES ('inventory_tank', p_label, COALESCE(p_status,'active'), p_by, p_volume_l, NULL)
    RETURNING id_uuid INTO rid;
  ELSE
    IF p_status='active' THEN
      PERFORM public.mark_container_active(rid, p_by);
    END IF;
    -- backfill volume if missing
    UPDATE public.containers
      SET tank_volume_l = COALESCE(tank_volume_l, p_volume_l)
    WHERE id_uuid = rid;
  END IF;

  RETURN rid;
END$$;

-- text wrapper (for clean SQLAlchemy calls)
CREATE OR REPLACE FUNCTION public.ensure_inventory_tank_v_text(
    p_label text, p_by text, p_status text, p_volume_l integer
) RETURNS uuid LANGUAGE plpgsql AS $$
BEGIN
  RETURN public.ensure_inventory_tank_v(p_label, p_by, p_status::container_status, p_volume_l);
END$$;

COMMIT;
