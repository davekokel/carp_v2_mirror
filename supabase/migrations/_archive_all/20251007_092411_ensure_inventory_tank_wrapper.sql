BEGIN;
CREATE OR REPLACE FUNCTION public.ensure_inventory_tank_text(p_label text, p_by text, p_status text)
RETURNS uuid LANGUAGE plpgsql AS $$
BEGIN
  RETURN public.ensure_inventory_tank(p_label, p_by, p_status::container_status);
END$$;
COMMIT;
