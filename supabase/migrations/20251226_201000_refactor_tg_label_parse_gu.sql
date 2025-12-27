BEGIN;

DROP VIEW IF EXISTS public.v11_roi_flat_table_display2;
DROP VIEW IF EXISTS public.v11_roi_flat_table_display;
DROP FUNCTION IF EXISTS public.parse_tg_label_pairs(text) CASCADE;
DROP FUNCTION IF EXISTS public.ensure_transgene_allele(text,text);


CREATE SEQUENCE IF NOT EXISTS public.global_allele_number_seq START 1;

SELECT setval(
  'public.global_allele_number_seq',
  GREATEST(
    COALESCE((SELECT max(allele_number) FROM public.transgene_alleles), 0) + 1,
    1
  ),
  false
);

DO $$
BEGIN
  IF NOT EXISTS (
    SELECT 1
    FROM pg_constraint
    WHERE conname = 'transgene_alleles_allele_number_unique'
      AND conrelid = 'public.transgene_alleles'::regclass
  ) THEN
    ALTER TABLE public.transgene_alleles
      ADD CONSTRAINT transgene_alleles_allele_number_unique UNIQUE (allele_number);
  END IF;
END $$;

CREATE UNIQUE INDEX IF NOT EXISTS transgene_alleles_base_nick_unique
ON public.transgene_alleles (transgene_base_code, allele_nickname)
WHERE coalesce(btrim(allele_nickname),'') <> '';

CREATE OR REPLACE FUNCTION public.norm_transgene_base_code(x text)
RETURNS text
LANGUAGE sql
IMMUTABLE
AS $$
  WITH s AS (
    SELECT lower(btrim(coalesce(x,''))) AS v
  )
  SELECT CASE
    WHEN (SELECT v FROM s) = '' THEN ''
    WHEN (SELECT v FROM s) ~ '^p([a-z]+)0*([0-9]+)$'
      THEN regexp_replace((SELECT v FROM s), '^p([a-z]+)0*([0-9]+)$', '\1-\2')
    WHEN (SELECT v FROM s) ~ '^([a-z]+)-?0*([0-9]+)$'
      THEN regexp_replace((SELECT v FROM s), '^([a-z]+)-?0*([0-9]+)$', '\1-\2')
    ELSE (SELECT v FROM s)
  END;
$$;

CREATE OR REPLACE FUNCTION public.ensure_transgene_allele(
  p_construct_code text,
  p_allele_nickname text
)
RETURNS TABLE (
  transgene_base_code text,
  allele_number int,
  allele_name text,
  allele_nickname text
)
LANGUAGE plpgsql
AS $$
DECLARE
  base text := public.norm_transgene_base_code(p_construct_code);
  nick text := btrim(coalesce(p_allele_nickname,''));
  n int;
  name text;
BEGIN
  IF base = '' THEN
    RETURN;
  END IF;

  IF nick <> '' THEN
    SELECT a.transgene_base_code, a.allele_number, a.allele_name, a.allele_nickname
    INTO transgene_base_code, allele_number, allele_name, allele_nickname
    FROM public.transgene_alleles a
    WHERE a.transgene_base_code = base
      AND btrim(coalesce(a.allele_nickname,'')) = nick
    LIMIT 1;

    IF FOUND THEN
      RETURN NEXT;
      RETURN;
    END IF;
  END IF;

  n := nextval('public.global_allele_number_seq')::int;
  name := 'gu' || n;

  IF nick = '' THEN
    nick := name;
  END IF;

  LOOP
    BEGIN
      INSERT INTO public.transgene_alleles (
        transgene_base_code,
        allele_number,
        allele_name,
        allele_nickname,
        created_at
      )
      VALUES (
        base,
        n,
        name,
        nick,
        now()
      );

      transgene_base_code := base;
      allele_number := n;
      allele_name := name;
      allele_nickname := nick;
      RETURN NEXT;
      RETURN;

    EXCEPTION
      WHEN unique_violation THEN
        IF EXISTS (
          SELECT 1
          FROM public.transgene_alleles a
          WHERE a.transgene_base_code = base
            AND btrim(coalesce(a.allele_nickname,'')) = nick
        ) THEN
          SELECT a.transgene_base_code, a.allele_number, a.allele_name, a.allele_nickname
          INTO transgene_base_code, allele_number, allele_name, allele_nickname
          FROM public.transgene_alleles a
          WHERE a.transgene_base_code = base
            AND btrim(coalesce(a.allele_nickname,'')) = nick
          LIMIT 1;

          RETURN NEXT;
          RETURN;
        END IF;

        n := nextval('public.global_allele_number_seq')::int;
        name := 'gu' || n;
        IF btrim(coalesce(in_allele_nickname,'')) = '' THEN
          nick := name;
        ELSE
          nick := btrim(in_allele_nickname);
        END IF;
    END;
  END LOOP;
END;
$$;

DROP VIEW IF EXISTS public.v11_roi_flat_table_display2;
DROP VIEW IF EXISTS public.v11_roi_flat_table_display;
DROP FUNCTION IF EXISTS public.parse_tg_label_pairs(text);

CREATE OR REPLACE FUNCTION public.parse_tg_label_pairs(tg_label text)
RETURNS TABLE (transgene_base_code text, allele_nickname text)
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
  base text;
  nick text;
BEGIN
  IF s = '' THEN
    RETURN;
  END IF;

  FOREACH seg IN ARRAY regexp_split_to_array(s, '\s*;\s*') LOOP
    seg := btrim(regexp_replace(coalesce(seg,''), '^.* >\s*', ''));
    IF seg = '' THEN
      CONTINUE;
    END IF;

    m := regexp_match(seg, '^\s*([a-z]+-?\d+(?:\|[a-z]+-?\d+)*)\s+([^\s]+(?:\|[^\s]+)*)\s*$', 'i');
    IF m IS NULL THEN
      CONTINUE;
    END IF;

    bases := regexp_split_to_array(lower(m[1]), '\|');
    alleles := regexp_split_to_array(m[2], '\|');

    IF array_length(bases,1) IS NULL OR array_length(alleles,1) IS NULL THEN
      CONTINUE;
    END IF;

    IF array_length(bases,1) <> array_length(alleles,1) THEN
      CONTINUE;
    END IF;

    FOR i IN 1..array_length(bases,1) LOOP
      base := public.norm_transgene_base_code(bases[i]);
      nick := btrim(coalesce(alleles[i],''));
      IF base = '' OR nick = '' THEN
        CONTINUE;
      END IF;
      transgene_base_code := base;
      allele_nickname := nick;
      RETURN NEXT;
    END LOOP;
  END LOOP;

  RETURN;
END;
$$;

CREATE OR REPLACE VIEW public.v11_roi_flat_table_display AS
SELECT
  t.experiment_date,
  t.experiment_name,
  t.plate_note,
  t.slot_note,
  t.slot_orientation,
  t.roi_id,
  t.roi_code,
  t.roi_index_within_slot,
  t.roi_note_anatomy,
  t.roi_path,
  ira.n_tiffs,
  t.clutch_code,
  count(DISTINCT t.treated_clutch_id) FILTER (WHERE t.treated_clutch_id IS NOT NULL) AS n_treated_clutches,
  string_agg(DISTINCT COALESCE(t.treated_clutch_code, tc.treated_clutch_code), '; ' ORDER BY (COALESCE(t.treated_clutch_code, tc.treated_clutch_code)))
    FILTER (WHERE COALESCE(t.treated_clutch_code, tc.treated_clutch_code) IS NOT NULL) AS treated_clutch_codes,
  string_agg(DISTINCT COALESCE(t.treatment_code, tr.treat_code), '; ' ORDER BY (COALESCE(t.treatment_code, tr.treat_code)))
    FILTER (WHERE COALESCE(t.treatment_code, tr.treat_code) IS NOT NULL) AS treatment_codes,
  string_agg(DISTINCT t.plasmids_display, '; ' ORDER BY t.plasmids_display) FILTER (WHERE t.plasmids_display IS NOT NULL) AS plasmids_display,
  string_agg(DISTINCT t.rnas_display, '; ' ORDER BY t.rnas_display) FILTER (WHERE t.rnas_display IS NOT NULL) AS rnas_display,
  string_agg(DISTINCT t.dyes_display, '; ' ORDER BY t.dyes_display) FILTER (WHERE t.dyes_display IS NOT NULL) AS dyes_display,

  string_agg(
    DISTINCT format('tg(%s)%s-%s', a.transgene_base_code, a.allele_name, a.allele_nickname),
    '; ' ORDER BY format('tg(%s)%s-%s', a.transgene_base_code, a.allele_name, a.allele_nickname)
  )
  FILTER (WHERE a.transgene_base_code IS NOT NULL) AS tx_gt_tg,

  string_agg(DISTINCT NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluortag, ''), '^.* > ', '')), ''), '; ' ORDER BY (NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluortag, ''), '^.* > ', '')), '')))
    FILTER (WHERE NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluortag, ''), '^.* > ', '')), '') IS NOT NULL) AS tx_gt_fluortag,

  string_agg(DISTINCT NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluororganelle, ''), '^.* > ', '')), ''), '; ' ORDER BY (NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluororganelle, ''), '^.* > ', '')), '')))
    FILTER (WHERE NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluororganelle, ''), '^.* > ', '')), '') IS NOT NULL) AS tx_gt_fluororganelle,

  ch.n_channels_total,
  ch.n_channels_kept,
  ch.kept_channels_key
FROM public.v11_roi_treatment_table_display t
LEFT JOIN public.imaging_roi_annotations ira ON ira.id = t.roi_id
LEFT JOIN public.imaging_clutch_memberships m ON m.slot_id = ira.slot_id
LEFT JOIN public.treated_clutches_v11 tc ON tc.id = m.treated_clutch_id
LEFT JOIN public.treatments tr ON tr.id = tc.treatment_id
LEFT JOIN public.v_imaging_roi_channel_qc_rollup_v2 ch ON ch.roi_id = t.roi_id
LEFT JOIN LATERAL public.parse_tg_label_pairs(t.tg_label) p ON true
LEFT JOIN public.transgene_alleles a
  ON a.transgene_base_code = p.transgene_base_code
 AND btrim(coalesce(a.allele_nickname,'')) = btrim(p.allele_nickname)
GROUP BY
  t.experiment_date, t.experiment_name, t.plate_note, t.slot_note, t.slot_orientation,
  t.roi_id, t.roi_code, t.roi_index_within_slot, t.roi_note_anatomy, t.roi_path, ira.n_tiffs,
  t.clutch_code, ch.n_channels_total, ch.n_channels_kept, ch.kept_channels_key;

COMMIT;
