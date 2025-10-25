-- Create helper schema + base36 function required by baseline_v2
CREATE SCHEMA IF NOT EXISTS util_mig;

CREATE OR REPLACE FUNCTION util_mig._to_base36(n bigint, width int DEFAULT 4)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
    digits TEXT := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    result TEXT := '';
    v BIGINT := n;
    r INT;
BEGIN
    IF n IS NULL OR n < 0 THEN
        RETURN NULL;
    END IF;

    IF v = 0 THEN
        result := '0';
    ELSE
        WHILE v > 0 LOOP
            r := (v % 36)::INT;
            result := substr(digits, r + 1, 1) || result;
            v := v / 36;
        END LOOP;
    END IF;

    WHILE length(result) < width LOOP
        result := '0' || result;
    END LOOP;

    RETURN result;
END;
$$;
