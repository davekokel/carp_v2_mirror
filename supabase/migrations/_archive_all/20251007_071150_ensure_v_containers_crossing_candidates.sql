BEGIN;

ALTER TABLE public.containers
DROP CONSTRAINT IF EXISTS chk_containers_type_allowed,
ADD CONSTRAINT chk_containers_type_allowed
CHECK (container_type IN ('inventory_tank', 'crossing_tank', 'holding_tank', 'nursery_tank', 'petri_dish'));

CREATE OR REPLACE VIEW public.v_containers_candidates AS
SELECT
    id_uuid,
    container_type,
    label,
    status,
    created_by,
    created_at,
    note
FROM public.containers
WHERE container_type IN ('inventory_tank', 'crossing_tank', 'holding_tank', 'nursery_tank', 'petri_dish');

COMMIT;
