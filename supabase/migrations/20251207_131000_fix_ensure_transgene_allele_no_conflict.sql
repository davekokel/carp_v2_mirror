BEGIN;

DROP FUNCTION IF EXISTS public.ensure_transgene_allele(text, text);

CREATE FUNCTION public.ensure_transgene_allele(
    p_construct_code   text,
    p_allele_nickname  text
)
RETURNS TABLE (
    transgene_base_code text,
    allele_number       integer,
    allele_name         text,
    allele_nickname     text
)
LANGUAGE plpgsql
AS $$
DECLARE
    v_base_code   text;
    v_nick        text;
    v_next_allele integer;
    v_name        text;
BEGIN
    -- 1) Resolve construct/base code to a canonical base_code from constructs
    SELECT c.base_code
    INTO v_base_code
    FROM public.constructs c
    WHERE c.base_code = p_construct_code
       OR c.construct_code = p_construct_code
    LIMIT 1;

    IF v_base_code IS NULL THEN
        RAISE EXCEPTION
            'ensure_transgene_allele: unknown construct/base code: % (not found in public.constructs.base_code or construct_code)',
            p_construct_code;
    END IF;

    v_nick := NULLIF(trim(p_allele_nickname), '');

    -- 2) Make sure there is a transgenes row for this base code
    INSERT INTO public.transgenes (transgene_base_code, created_at)
    SELECT v_base_code, now()
    WHERE NOT EXISTS (
        SELECT 1
        FROM public.transgenes t
        WHERE t.transgene_base_code = v_base_code
    );

    -- 3) Try to reuse an existing allele if nickname is provided and exists
    IF v_nick IS NOT NULL THEN
        SELECT
            ta.transgene_base_code,
            ta.allele_number,
            ta.allele_name,
            ta.allele_nickname
        INTO
            transgene_base_code,
            allele_number,
            allele_name,
            allele_nickname
        FROM public.transgene_alleles ta
        WHERE ta.transgene_base_code = v_base_code
          AND ta.allele_nickname = v_nick
        LIMIT 1;

        IF FOUND THEN
            RETURN NEXT;
            RETURN;
        END IF;
    END IF;

    -- 4) No reusable allele: mint a new canonical allele_number
    SELECT nextval('public.transgene_alleles_allele_number_seq')
    INTO v_next_allele;

    v_name := 'gu' || v_next_allele;
    IF v_nick IS NULL THEN
        v_nick := v_name;
    END IF;

    INSERT INTO public.transgene_alleles (
        transgene_base_code,
        allele_number,
        allele_name,
        allele_nickname,
        created_at
    )
    VALUES (
        v_base_code,
        v_next_allele,
        v_name,
        v_nick,
        now()
    );

    -- 5) Return the canonical row we just inserted
    transgene_base_code := v_base_code;
    allele_number       := v_next_allele;
    allele_name         := v_name;
    allele_nickname     := v_nick;

    RETURN NEXT;
END;
$$;

COMMENT ON FUNCTION public.ensure_transgene_allele(text, text) IS
'Allocate or reuse a transgene allele for a given construct/base code and nickname, front-filling public.transgenes (via constructs.base_code) and assigning a global canonical allele_number.';

COMMIT;
