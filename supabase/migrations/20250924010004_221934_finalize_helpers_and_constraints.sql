-- finalize_helpers_and_constraints (clean safe version)

-- Ensure sequences exist
CREATE SEQUENCE IF NOT EXISTS public.auto_fish_seq;
CREATE SEQUENCE IF NOT EXISTS public.tank_label_seq;

-- Ensure next_tank_code has stable signature p_prefix text
DO $$
BEGIN
  -- Drop any variants to avoid signature/arg-name conflicts
  EXECUTE 'DROP FUNCTION IF EXISTS public.next_tank_code(text)';
  EXECUTE 'DROP FUNCTION IF EXISTS public.next_tank_code(p_prefix text)';
END$$;

CREATE OR REPLACE FUNCTION public.next_tank_code(p_prefix text)
RETURNS text
LANGUAGE plpgsql
AS $func$
DECLARE
  n bigint;
BEGIN
  n := nextval('public.tank_label_seq');
  RETURN p_prefix || to_char(n, 'FM000');
END
$func$;

-- Guarded grants: only grant if relation exists
DO $$
BEGIN
  IF to_regclass('public.v_fish_overview_v1') IS NOT NULL THEN
    EXECUTE 'GRANT SELECT ON public.v_fish_overview_v1 TO anon, authenticated';
  END IF;

  IF to_regclass('public.fish') IS NOT NULL THEN
    EXECUTE 'GRANT SELECT ON public.fish TO anon, authenticated';
  END IF;

  IF to_regclass('public.transgenes') IS NOT NULL THEN
    EXECUTE 'GRANT SELECT ON public.transgenes TO anon, authenticated';
  END IF;

  IF to_regclass('public.fish_transgene_alleles') IS NOT NULL THEN
    EXECUTE 'GRANT SELECT ON public.fish_transgene_alleles TO anon, authenticated';
  END IF;

  IF to_regclass('public.treatments') IS NOT NULL THEN
    EXECUTE 'GRANT SELECT ON public.treatments TO anon, authenticated';
  END IF;

  IF to_regclass('public.fish_treatments') IS NOT NULL THEN
    EXECUTE 'GRANT SELECT ON public.fish_treatments TO anon, authenticated';
  END IF;

  IF to_regclass('public.tank_assignments') IS NOT NULL THEN
    EXECUTE 'GRANT SELECT ON public.tank_assignments TO anon, authenticated';
  END IF;

  IF to_regclass('public.transgene_allele_catalog') IS NOT NULL THEN
    EXECUTE 'GRANT SELECT ON public.transgene_allele_catalog TO anon, authenticated';
  END IF;
END$$;
