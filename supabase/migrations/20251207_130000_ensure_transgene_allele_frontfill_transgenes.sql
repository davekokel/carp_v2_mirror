BEGIN;

-- Always replace the allocator with the frontfill-aware version.
DROP FUNCTION IF EXISTS public.ensure_transgene_allele(text, text);

CREATE FUNCTION public.ensure_transgene_allele(
    p_construct_code   text,
    p_allele_nickname  text
) RETURNS TABLE (
    transgene_base_code text,
    allele_number       integer,
    allele_name         text,
    allele_nickname     text
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_input_code   text;
    v_base_code    text;
    v_nick         text;
    v_existing     public.transgene_alleles%ROWTYPE;
    v_next_allele  integer;
    v_name         text;
BEGIN
    -- 1) Normalize the incoming construct / base code token
    v_input_code := trim(p_construct_code);
    v_nick       := NULLIF(trim(p_allele_nickname), '');

    IF v_input_code IS NULL OR v_input_code = '' THEN
        RAISE EXCEPTION 'ensure_transgene_allele: construct/base code is required';
    END IF;

    -- Resolve to a canonical base_code in public.constructs (case-insensitive)
    SELECT lower(c.base_code)
      INTO v_base_code
      FROM public.constructs c
     WHERE lower(c.base_code)      = lower(v_input_code)
        OR lower(c.construct_code) = lower(v_input_code)
        OR lower(c.nickname)       = lower(v_input_code)
     ORDER BY c.base_code
     LIMIT 1;

    IF v_base_code IS NULL THEN
        RAISE EXCEPTION
          'ensure_transgene_allele: no matching construct/base code for %',
          p_construct_code;
    END IF;

    -- 2) Ensure a public.transgenes row exists for this base code (frontfill)
    INSERT INTO public.transgenes (transgene_base_code, created_at)
    VALUES (v_base_code, now())
    ON CONFLICT (transgene_base_code) DO NOTHING;

    -- 3) If we have a nickname, try to reuse an existing allele
    IF v_nick IS NOT NULL THEN
        SELECT *
          INTO v_existing
          FROM public.transgene_alleles a
         WHERE a.transgene_base_code = v_base_code
           AND a.allele_nickname     = v_nick
         LIMIT 1;

        IF FOUND THEN
            transgene_base_code := v_existing.transgene_base_code;
            allele_number       := v_existing.allele_number;
            allele_name         := v_existing.allele_name;
            allele_nickname     := v_existing.allele_nickname;
            RETURN NEXT;
            RETURN;
        END IF;
    END IF;

    -- 4) Allocate a new global allele_number and name
    SELECT nextval('public.transgene_alleles_allele_number_seq')
      INTO v_next_allele;

    -- Example naming: a0001, a0002, ...
    v_name := 'a' || to_char(v_next_allele, 'FM000');

    INSERT INTO public.transgene_alleles (
        transgene_base_code,
        allele_number,
        allele_name,
        allele_nickname
    )
    VALUES (
        v_base_code,
        v_next_allele,
        v_name,
        COALESCE(v_nick, v_name)
    )
    RETURNING
        transgene_base_code,
        allele_number,
        allele_name,
        allele_nickname
      INTO
        transgene_base_code,
        allele_number,
        allele_name,
        allele_nickname;

    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.ensure_transgene_allele(text, text) IS
    'Allocate or reuse a transgene allele for a given construct/base code and nickname, front-filling public.transgenes as needed.';

COMMIT;
