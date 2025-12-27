CREATE OR REPLACE FUNCTION public.parse_tg_label_pairs(tg_label text)
RETURNS TABLE(transgene_base_code text, allele_number int)
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
  allele_txt text;
  allele_int int;
  r text[];
BEGIN
  IF s = '' THEN
    RETURN;
  END IF;

  s := btrim(regexp_replace(s, '^.*>\s*', ''));

  FOREACH seg IN ARRAY regexp_split_to_array(s, '\s*;\s*') LOOP
    seg := btrim(seg);
    IF seg = '' THEN
      CONTINUE;
    END IF;

    m := regexp_match(seg, '^\s*([a-z]+-?\d+(?:\|[a-z]+-?\d+)*)\s+([0-9]+(?:\|[0-9]+)*)\s*$', 'i');
    IF m IS NOT NULL THEN
      bases := regexp_split_to_array(lower(m[1]), '\|');
      alleles := regexp_split_to_array(m[2], '\|');

      IF array_length(bases,1) IS NOT NULL
         AND array_length(alleles,1) IS NOT NULL
         AND array_length(bases,1) = array_length(alleles,1) THEN

        FOR i IN 1..array_length(bases,1) LOOP
          base := lower(btrim(bases[i]));
          allele_txt := btrim(alleles[i]);

          BEGIN
            allele_int := allele_txt::int;
          EXCEPTION WHEN others THEN
            CONTINUE;
          END;

          transgene_base_code := base;
          allele_number := allele_int;
          RETURN NEXT;
        END LOOP;

        CONTINUE;
      END IF;
    END IF;

    FOR r IN
      SELECT x
      FROM regexp_matches(seg, 'tg\(\s*([a-z]+-?\d+)\s*\)[^;]*?-([0-9]+)', 'gi') AS x
    LOOP
      base := lower(btrim(r[1]));

      BEGIN
        allele_int := btrim(r[2])::int;
      EXCEPTION WHEN others THEN
        CONTINUE;
      END;

      transgene_base_code := base;
      allele_number := allele_int;
      RETURN NEXT;
    END LOOP;

    CONTINUE;
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
    DISTINCT format('tg(%s)%s-%s', a.transgene_base_code, a.allele_nickname, a.allele_number),
    '; ' ORDER BY format('tg(%s)%s-%s', a.transgene_base_code, a.allele_nickname, a.allele_number)
  )
  FILTER (
    WHERE a.transgene_base_code IS NOT NULL
      AND nullif(btrim(a.allele_nickname),'') IS NOT NULL
  ) AS tx_gt_tg,

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
 AND a.allele_number = p.allele_number
GROUP BY
  t.experiment_date, t.experiment_name, t.plate_note, t.slot_note, t.slot_orientation,
  t.roi_id, t.roi_code, t.roi_index_within_slot, t.roi_note_anatomy, t.roi_path, ira.n_tiffs,
  t.clutch_code, ch.n_channels_total, ch.n_channels_kept, ch.kept_channels_key;
