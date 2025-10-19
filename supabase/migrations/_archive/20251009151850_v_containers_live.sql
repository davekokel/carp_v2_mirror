BEGIN;

CREATE OR REPLACE VIEW public.v_containers_live AS
SELECT *
FROM public.containers
WHERE status IN ('active', 'new_tank');

-- optional helper if you like function form
CREATE OR REPLACE FUNCTION public.is_container_live(s text)
RETURNS boolean LANGUAGE sql IMMUTABLE AS $$
  select s in ('active','new_tank')
$$;

COMMIT;
