BEGIN;

DROP FUNCTION IF EXISTS public.upsert_fish_allele_from_csv(uuid, text, text);

CREATE FUNCTION public.upsert_fish_allele_from_csv(
  p_fish_id   uuid,
  p_base_code text,
  p_allele    text
)
RETURNS TABLE(ok boolean, action text, msg text)
LANGUAGE plpgsql
AS $$
DECLARE
  -- join_fish_transgene_alleles shape
  has_fish_uuid    boolean;
  has_fish_id      boolean;
  has_alle_nick    boolean;
  has_alle_num     boolean;
  allele_num_nn    boolean;  -- allele_number NOT NULL?

  v_base   text := NULLIF(btrim(coalesce(p_base_code,'')), '');
  v_alle_s text := NULLIF(btrim(coalesce(p_allele,'')), '');
  v_alle_i integer;

  exists_sql text;
  exists_any boolean;

  ins_cols text[];
  ins_vals text[];
  ins_sql  text;
BEGIN
  IF p_fish_id IS NULL THEN
    RETURN QUERY SELECT false, 'error', 'fish_id is required';
    RETURN;
  END IF;
  IF v_base IS NULL THEN
    RETURN QUERY SELECT false, 'skip', 'no base_code provided';
    RETURN;
  END IF;

  SELECT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_uuid')
    INTO has_fish_uuid;

  SELECT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='fish_id')
    INTO has_fish_id;

  SELECT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='allele_nickname')
    INTO has_alle_nick;

  SELECT EXISTS (SELECT 1 FROM information_schema.columns
                 WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='allele_number')
    INTO has_alle_num;

  SELECT (is_nullable='NO') FROM information_schema.columns
    WHERE table_schema='public' AND table_name='join_fish_transgene_alleles' AND column_name='allele_number'
    INTO allele_num_nn;

  IF NOT (has_fish_uuid OR has_fish_id) THEN
    RETURN QUERY SELECT false, 'error', 'join_fish_transgene_alleles missing fish_uuid/fish_id';
    RETURN;
  END IF;

  -- If allele_number exists and is NOT NULL, require a numeric allele
  IF has_alle_num AND allele_num_nn THEN
    IF v_alle_s IS NULL THEN
      RETURN QUERY SELECT false, 'error', 'allele_number is required';
      RETURN;
    END IF;
    BEGIN
      v_alle_i := v_alle_s::int;
    EXCEPTION WHEN others THEN
      RETURN QUERY SELECT false, 'error', 'allele_number must be an integer';
      RETURN;
    END;
  ELSE
    -- optional integer parse; ok if NULL/non-numeric when not required
    IF v_alle_s IS NOT NULL THEN
      BEGIN
        v_alle_i := v_alle_s::int;
      EXCEPTION WHEN others THEN
        v_alle_i := NULL;
      END;
    END IF;
  END IF;

  -- Dedup check
  IF has_alle_nick THEN
    exists_sql := format(
      'SELECT EXISTS(
         SELECT 1 FROM public.join_fish_transgene_alleles j
         WHERE j.%I = %L AND j.transgene_base_code=%L AND NULLIF(j.allele_nickname,'''') IS NOT DISTINCT FROM %L
       )',
      CASE WHEN has_fish_uuid THEN 'fish_uuid' ELSE 'fish_id' END,
      p_fish_id, v_base, v_alle_s
    );
  ELSIF has_alle_num THEN
    exists_sql := format(
      'SELECT EXISTS(
         SELECT 1 FROM public.join_fish_transgene_alleles j
         WHERE j.%I = %L AND j.transgene_base_code=%L AND j.allele_number IS NOT DISTINCT FROM %s
       )',
      CASE WHEN has_fish_uuid THEN 'fish_uuid' ELSE 'fish_id' END,
      p_fish_id, v_base,
      CASE WHEN v_alle_i IS NULL THEN 'NULL' ELSE quote_literal(v_alle_i) END
    );
  ELSE
    exists_sql := format(
      'SELECT EXISTS(
         SELECT 1 FROM public.join_fish_transgene_alleles j
         WHERE j.%I = %L AND j.transgene_base_code=%L
       )',
      CASE WHEN has_fish_uuid THEN 'fish_uuid' ELSE 'fish_id' END,
      p_fish_id, v_base
    );
  END IF;

  EXECUTE exists_sql INTO exists_any;
  IF exists_any THEN
    RETURN QUERY SELECT true, 'noop', 'link already present';
    RETURN;
  END IF;

  -- Build INSERT dynamically
  ins_cols := ARRAY[ CASE WHEN has_fish_uuid THEN 'fish_uuid' ELSE 'fish_id' END, 'transgene_base_code' ];
  ins_vals := ARRAY[ quote_literal(p_fish_id), quote_literal(v_base) ];

  IF has_alle_nick AND v_alle_s IS NOT NULL THEN
    ins_cols := ins_cols || 'allele_nickname';
    ins_vals := ins_vals || quote_literal(v_alle_s);
  ELSIF has_alle_num THEN
    -- If column exists, include integer value (may be NULL if nullable)
    ins_cols := ins_cols || 'allele_number';
    ins_vals := ins_vals || CASE WHEN v_alle_i IS NULL THEN 'NULL' ELSE quote_literal(v_alle_i) END;
  END IF;

  ins_sql := format(
    'INSERT INTO public.join_fish_transgene_alleles(%s) VALUES(%s)',
    array_to_string(ARRAY(SELECT format('%I', c) FROM unnest(ins_cols) AS c), ','),
    array_to_string(ins_vals, ',')
  );
  EXECUTE ins_sql;

  RETURN QUERY SELECT true, 'insert', 'allele link created';
END;
$$;

COMMIT;
