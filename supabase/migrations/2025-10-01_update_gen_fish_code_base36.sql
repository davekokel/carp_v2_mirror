-- Updates gen_fish_code to use base36 suffix
CREATE OR REPLACE FUNCTION public.gen_fish_code(p_ts timestamp with time zone DEFAULT now())
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
    y int := extract(year from p_ts);
    k int;
BEGIN
    INSERT INTO public.fish_year_counters(year, n)
    VALUES (y, 0)
    ON CONFLICT (year) DO NOTHING;

    UPDATE public.fish_year_counters
    SET n = n + 1
    WHERE year = y
    RETURNING n INTO k;

    RETURN format('FSH-%s-%s', y, lpad(to_base36(k), 3, '0'));
END;
$$;
