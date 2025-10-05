BEGIN;

-- Fix _to_base36: cast substr index to int (Postgres requires int, not bigint)
CREATE OR REPLACE FUNCTION public._to_base36(n bigint, pad int)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE AS $$
DECLARE
  chars CONSTANT text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
  x bigint := n;
  out text := '';
  idx int;
BEGIN
  IF x < 0 THEN RAISE EXCEPTION 'negative not allowed'; END IF;
  IF x = 0 THEN
    out := '0';
  ELSE
    WHILE x > 0 LOOP
      idx := ((x % 36)::int) + 1;         -- cast to int for substr()
      out := substr(chars, idx, 1) || out;
      x := x / 36;
    END LOOP;
  END IF;
  IF length(out) < pad THEN
    out := lpad(out, pad, '0');
  END IF;
  RETURN out;
END $$;

COMMIT;
