BEGIN;

-- Drop any existing checks on container_type (old names & our newer one)
ALTER TABLE public.containers
DROP CONSTRAINT IF EXISTS containers_container_type_check,
DROP CONSTRAINT IF EXISTS chk_containers_type_allowed;

-- Re-add the allowed set you specified
ALTER TABLE public.containers
ADD CONSTRAINT chk_containers_type_allowed
CHECK (container_type IN ('inventory_tank', 'crossing_tank', 'holding_tank', 'nursery_tank', 'petri_dish'));

COMMIT;
