CREATE OR REPLACE FUNCTION public.tx_gt_tg_from_label(tg_label text)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
  s text := btrim(coalesce(tg_label,''));
  seg text;
  m text[];
  bases text[];
  alleles text[];
  i int;
  out_parts text[] := ARRAY[]::text[];
BEGIN
  IF s = '' THEN
    RETURN '';
  END IF;

  FOREACH seg IN ARRAY regexp_split_to_array(s, '\s*;\s*')
  LOOP
    seg := btrim(seg);
    IF seg = '' THEN
      CONTINUE;
    END IF;

    m := regexp_match(seg, '^\s*([a-z]+-\d+(?:\|[a-z]+-\d+)*)\s+([0-9]+(?:\|[0-9]+)*)\s*$', 'i');
    IF m IS NOT NULL THEN
      bases := regexp_split_to_array(lower(m[1]), '\|');
      alleles := regexp_split_to_array(m[2], '\|');

      IF array_length(bases,1) IS NOT NULL AND array_length(alleles,1) IS NOT NULL
         AND array_length(bases,1) = array_length(alleles,1) THEN
        FOR i IN 1..array_length(bases,1) LOOP
          out_parts := array_append(out_parts, format('tg(%s)allele_number-%s', bases[i], alleles[i]));
        END LOOP;
        CONTINUE;
      END IF;
    END IF;

    bases := ARRAY(
      SELECT lower(x[1] || '-' || x[2])
      FROM regexp_matches(seg, '([a-z]+)-?0*([0-9]+)', 'gi') AS x
    );
    IF bases IS NOT NULL AND array_length(bases,1) IS NOT NULL THEN
      FOR i IN 1..array_length(bases,1) LOOP
        out_parts := array_append(out_parts, format('tg %s', bases[i]));
      END LOOP;
    END IF;
  END LOOP;

  RETURN array_to_string(out_parts, '; ');
END;
$$;
