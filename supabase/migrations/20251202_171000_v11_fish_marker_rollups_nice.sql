BEGIN;

CREATE OR REPLACE FUNCTION public.normalize_marker_rollup(raw text)
RETURNS text
LANGUAGE plpgsql
AS $$
DECLARE
  part text;
  fluor text;
  tag_pos text;
  clean_parts text[];
BEGIN
  IF raw IS NULL OR btrim(raw) = '' THEN
    RETURN '';
  END IF;

  clean_parts := ARRAY[]::text[];

  FOR part IN
    SELECT DISTINCT btrim(x)
    FROM unnest(string_to_array(raw, '||')) AS x
    WHERE btrim(x) <> ''
  LOOP
    IF part LIKE '%::%' THEN
      fluor := split_part(part, '::', 1);
      tag_pos := split_part(part, '::', 2);
    ELSE
      fluor := part;
      tag_pos := '';
    END IF;

    fluor := btrim(fluor);
    tag_pos := btrim(tag_pos);

    IF fluor = '' THEN
      CONTINUE;
    END IF;

    IF tag_pos = '' THEN
      clean_parts := clean_parts || format('%s::()', fluor);
    ELSE
      clean_parts := clean_parts || format('%s::%s', fluor, tag_pos);
    END IF;
  END LOOP;

  IF array_length(clean_parts, 1) IS NULL THEN
    RETURN '';
  END IF;

  RETURN array_to_string(clean_parts, '||');
END;
$$;

CREATE OR REPLACE VIEW public.v11_fish_marker_rollups_nice AS
SELECT
  m.fish_instance_id,
  m.n_constructs,
  m.n_fluors,
  public.normalize_marker_rollup(m.fluor_tag_rollup)       AS fluor_tag_rollup,
  public.normalize_marker_rollup(m.organelle_fluor_rollup) AS organelle_fluor_rollup
FROM public.v11_fish_marker_rollups m;

COMMENT ON VIEW public.v11_fish_marker_rollups_nice IS
'Cleaned marker rollups derived from v11_fish_marker_rollups; fluor::tag(tag_pos) normalized and de-duplicated.';

COMMIT;
