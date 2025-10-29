-- 20251029_120500_util_mig_to_base36.sql
-- Restore the util_mig helper schema and base-36 conversion function used by fish-code generators.

create schema if not exists util_mig;

create or replace function util_mig.to_base36(val bigint, pad int)
returns text
language plpgsql
as $$
declare
    chars text := '0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ';
    result text := '';
    n bigint := val;
begin
    if n is null then
        return null;
    end if;
    if n = 0 then
        result := '0';
    else
        while n > 0 loop
            result := substr(chars, (n % 36)+1, 1) || result;
            n := n / 36;
        end loop;
    end if;
    if pad > 0 then
        result := lpad(result, pad, '0');
    end if;
    return result;
end
$$;
