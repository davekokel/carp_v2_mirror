BEGIN;

CREATE OR REPLACE VIEW public.v_fish_living_tank_counts AS
SELECT
    m.fish_id,
    count(*)::int AS n_living_tanks
FROM public.fish_tank_memberships AS m
INNER JOIN public.containers AS c ON m.container_id = c.id_uuid
WHERE
    m.left_at IS null
    AND c.status IN ('active', 'new_tank')
GROUP BY m.fish_id;

CREATE INDEX IF NOT EXISTS idx_ftm_fish_id ON public.fish_tank_memberships (fish_id);

COMMIT;
