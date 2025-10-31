-- Use md5(uuid::text) to derive a stable 64-bit advisory lock key
CREATE OR REPLACE FUNCTION public.next_clutch_seq(p_cross_id uuid)
RETURNS smallint
LANGUAGE plpgsql
AS $$
DECLARE
  v smallint;
  k bigint;
BEGIN
  -- stable 64-bit key from first 16 hex chars of md5(uuid::text)
  SELECT ( 'x' || substr(md5(p_cross_id::text), 1, 16) )::bit(64)::bigint
    INTO k;

  PERFORM pg_advisory_xact_lock(k);

  SELECT COALESCE(MAX(clutch_seq), 0) + 1
    INTO v
    FROM public.clutch_instances
   WHERE cross_instance_id = p_cross_id;

  RETURN v;
END
$$;

-- keep trigger in place (no-op if it already exists)
-- it calls next_clutch_seq() and formats ...-C01/02...
