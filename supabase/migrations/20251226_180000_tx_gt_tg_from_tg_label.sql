CREATE OR REPLACE FUNCTION public.tx_gt_tg_from_label(tg_label text)
RETURNS text
LANGUAGE plpgsql
IMMUTABLE
AS $$
DECLARE
  m text[];
  bases text[] := ARRAY[]::text[];
  alleles text[] := ARRAY[]::text[];
  seen_base text[] := ARRAY[]::text[];
  b text;
  a text;
  i int;
BEGIN
  IF tg_label IS NULL OR btrim(tg_label) = '' THEN
    RETURN NULL;
  END IF;

  FOR m IN
    SELECT regexp_matches(lower(tg_label), '(pdqm|mgco|hc|pswin|swin)\s*-?\s*0*([0-9]+)', 'g')
  LOOP
    b := CASE WHEN m[1] = 'swin' THEN 'pswin' ELSE m[1] END || '-' || (m[2]::int)::text;
    IF NOT (b = ANY(seen_base)) THEN
      seen_base := array_append(seen_base, b);
      bases := array_append(bases, b);
    END IF;
  END LOOP;

  IF coalesce(array_length(bases, 1), 0) = 0 THEN
    RETURN NULL;
  END IF;

  FOR m IN
    SELECT regexp_matches(lower(tg_label), 'allele\s*0*([0-9]+)', 'g')
  LOOP
    alleles := array_append(alleles, (m[1]::int)::text);
  END LOOP;

  IF coalesce(array_length(alleles, 1), 0) = array_length(bases, 1) AND array_length(bases, 1) > 0 THEN
    RETURN (
      SELECT string_agg(format('tg(%s)%s', bases[i], alleles[i]), '; ' ORDER BY i)
      FROM generate_subscripts(bases, 1) AS s(i)
    );
  END IF;

  RETURN (
    SELECT string_agg(format('tg %s', bases[i]), '; ' ORDER BY i)
    FROM generate_subscripts(bases, 1) AS s(i)
  );
END;
$$;

CREATE OR REPLACE VIEW public.v11_roi_flat_table_display AS
 SELECT t.experiment_date,
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
    string_agg(DISTINCT COALESCE(t.treated_clutch_code, tc.treated_clutch_code), '; '::text ORDER BY (COALESCE(t.treated_clutch_code, tc.treated_clutch_code))) FILTER (WHERE COALESCE(t.treated_clutch_code, tc.treated_clutch_code) IS NOT NULL) AS treated_clutch_codes,
    string_agg(DISTINCT COALESCE(t.treatment_code, tr.treat_code), '; '::text ORDER BY (COALESCE(t.treatment_code, tr.treat_code))) FILTER (WHERE COALESCE(t.treatment_code, tr.treat_code) IS NOT NULL) AS treatment_codes,
    string_agg(DISTINCT t.plasmids_display, '; '::text ORDER BY t.plasmids_display) FILTER (WHERE t.plasmids_display IS NOT NULL) AS plasmids_display,
    string_agg(DISTINCT t.rnas_display, '; '::text ORDER BY t.rnas_display) FILTER (WHERE t.rnas_display IS NOT NULL) AS rnas_display,
    string_agg(DISTINCT t.dyes_display, '; '::text ORDER BY t.dyes_display) FILTER (WHERE t.dyes_display IS NOT NULL) AS dyes_display,
    string_agg(
      DISTINCT NULLIF(
        btrim(
          regexp_replace(
            COALESCE(public.tx_gt_tg_from_label(t.tg_label), COALESCE(t.tx_gt_tg, ''::text)),
            '^.* > '::text,
            ''::text
          )
        ),
        ''::text
      ),
      '; '::text
      ORDER BY (
        NULLIF(
          btrim(
            regexp_replace(
              COALESCE(public.tx_gt_tg_from_label(t.tg_label), COALESCE(t.tx_gt_tg, ''::text)),
              '^.* > '::text,
              ''::text
            )
          ),
          ''::text
        )
      )
    ) FILTER (WHERE NULLIF(btrim(regexp_replace(COALESCE(public.tx_gt_tg_from_label(t.tg_label), COALESCE(t.tx_gt_tg, ''::text)), '^.* > '::text, ''::text)), ''::text) IS NOT NULL) AS tx_gt_tg,
    string_agg(DISTINCT NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluortag, ''::text), '^.* > '::text, ''::text)), ''::text), '; '::text ORDER BY (NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluortag, ''::text), '^.* > '::text, ''::text)), ''::text))) FILTER (WHERE NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluortag, ''::text), '^.* > '::text, ''::text)), ''::text) IS NOT NULL) AS tx_gt_fluortag,
    string_agg(DISTINCT NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluororganelle, ''::text), '^.* > '::text, ''::text)), ''::text), '; '::text ORDER BY (NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluororganelle, ''::text), '^.* > '::text, ''::text)), ''::text))) FILTER (WHERE NULLIF(btrim(regexp_replace(COALESCE(t.tx_gt_fluororganelle, ''::text), '^.* > '::text, ''::text)), ''::text) IS NOT NULL) AS tx_gt_fluororganelle,
    ch.n_channels_total,
    ch.n_channels_kept,
    ch.kept_channels_key
   FROM public.v11_roi_treatment_table_display t
     LEFT JOIN public.imaging_roi_annotations ira ON ira.id = t.roi_id
     LEFT JOIN public.imaging_clutch_memberships m ON m.slot_id = ira.slot_id
     LEFT JOIN public.treated_clutches_v11 tc ON tc.id = m.treated_clutch_id
     LEFT JOIN public.treatments tr ON tr.id = tc.treatment_id
     LEFT JOIN public.v_imaging_roi_channel_qc_rollup_v2 ch ON ch.roi_id = t.roi_id
  GROUP BY t.experiment_date, t.experiment_name, t.plate_note, t.slot_note, t.slot_orientation, t.roi_id, t.roi_code, t.roi_index_within_slot, t.roi_note_anatomy, t.roi_path, ira.n_tiffs, t.clutch_code, ch.n_channels_total, ch.n_channels_kept, ch.kept_channels_key;
