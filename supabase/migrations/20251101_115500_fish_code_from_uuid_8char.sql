BEGIN;

ALTER TABLE public.fish
  ADD COLUMN IF NOT EXISTS fish_code text;

CREATE UNIQUE INDEX IF NOT EXISTS uq_fish_fish_code ON public.fish(fish_code);

CREATE OR REPLACE FUNCTION public._to_base36(p_val bigint, p_width int DEFAULT 8)
RETURNS text
LANGUAGE plpgsql IMMUTABLE STRICT AS $$
DECLARE
  v numeric := p_val;
  out text := '';
  digits constant text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
BEGIN
  IF v < 0 THEN RAISE EXCEPTION 'to_base36 expects non-negative'; END IF;
  IF v = 0 THEN out := '0'; END IF;
  WHILE v > 0 LOOP
    out := substr(digits, (v % 36)::int + 1, 1) || out;
    v := floor(v / 36);
  END LOOP;
  IF length(out) < p_width THEN
    out := lpad(out, p_width, '0');
  END IF;
  RETURN out;
END $$;

CREATE OR REPLACE FUNCTION public._short8_from_uuid(p uuid)
RETURNS text
LANGUAGE sql IMMUTABLE STRICT AS $$
  SELECT public._to_base36(('x' || replace(p::text,'-',''))::bit(40)::bigint, 8)
$$;

CREATE OR REPLACE FUNCTION public._next_fish_code_from_uuid(p uuid)
RETURNS text
LANGUAGE plpgsql VOLATILE AS $$
DECLARE
  code text;
  extra text;
BEGIN
  code := 'FSH-' || public._short8_from_uuid(p);
  code := replace(replace(replace(code,'O','0'),'I','1'),'L','1');
  IF NOT EXISTS (SELECT 1 FROM public.fish WHERE fish_code = code) THEN
    RETURN code;
  END IF;

  extra := public._to_base36(('x' || right(replace(p::text,'-',''),8))::bit(8)::bigint, 2);
  code := code || substr(extra,1,1);
  IF NOT EXISTS (SELECT 1 FROM public.fish WHERE fish_code = code) THEN
    RETURN code;
  END IF;

  RETURN code || substr(public._to_base36((random()*36)::int, 1), 1, 1);
END $$;

CREATE OR REPLACE FUNCTION public.ensure_fish_code()
RETURNS trigger
LANGUAGE plpgsql AS $$
BEGIN
  IF NEW.fish_code IS NULL OR NEW.fish_code = '' THEN
    NEW.fish_code := public._next_fish_code_from_uuid(NEW.id);
  END IF;
  RETURN NEW;
END $$;

DROP TRIGGER IF EXISTS trg_fish_ensure_code ON public.fish;
CREATE TRIGGER trg_fish_ensure_code
BEFORE INSERT ON public.fish
FOR EACH ROW
EXECUTE FUNCTION public.ensure_fish_code();

WITH gen AS (
  SELECT id, public._next_fish_code_from_uuid(id) AS code
  FROM public.fish
  WHERE fish_code IS NULL OR fish_code = ''
)
UPDATE public.fish f
SET fish_code = g.code
FROM gen g
WHERE g.id = f.id;

COMMIT;
