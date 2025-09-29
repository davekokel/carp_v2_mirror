CREATE SEQUENCE IF NOT EXISTS public.auto_fish_seq;

CREATE OR REPLACE FUNCTION public.next_auto_fish_code()
RETURNS text
LANGUAGE sql
AS $$
  SELECT 'FSH-' || to_char(now(), 'YYYY') || '-' || to_char(nextval('public.auto_fish_seq'), 'FM000');
$$;
