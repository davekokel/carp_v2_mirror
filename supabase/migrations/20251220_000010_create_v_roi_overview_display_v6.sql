create or replace view public.v_roi_overview_display_v6 as
with base as (
  select *
  from public.v_roi_overview_rollups_fix
),
ingredients as (
  select
    t.treat_code as treatment_code,
    tmc.delivery_form,

    string_agg(
      distinct coalesce(nullif(btrim(vo.fusion_pretty), ''), c.construct_code),
      ', ' order by coalesce(nullif(btrim(vo.fusion_pretty), ''), c.construct_code)
    ) as codes_fluortag,

    string_agg(
      distinct coalesce(nullif(btrim(vo.organelle_fluors), ''), c.construct_code),
      ', ' order by coalesce(nullif(btrim(vo.organelle_fluors), ''), c.construct_code)
    ) as codes_fluororganelle,

    string_agg(
      distinct coalesce(nullif(btrim(vo.fusion_pretty), ''), c.construct_code),
      ', ' order by coalesce(nullif(btrim(vo.fusion_pretty), ''), c.construct_code)
    ) as codes_tg
  from public.treatments t
  join public.treatment_mixes tm
    on tm.treatment_id = t.id
  join public.treatment_mix_constructs tmc
    on tmc.mix_id = tm.id
  join public.constructs c
    on c.id = tmc.construct_id
  left join public.v_constructs_overview vo
    on lower(vo.construct_code) = lower(c.construct_code)
  group by t.treat_code, tmc.delivery_form
),
treatment_pretty as (
  select
    treatment_code,
    string_agg(delivery_form || '(' || codes_fluortag || ')', '; ' order by delivery_form) as treatment_pretty_fluortag,
    string_agg(delivery_form || '(' || codes_fluororganelle || ')', '; ' order by delivery_form) as treatment_pretty_fluororganelle,
    string_agg(delivery_form || '(' || codes_tg || ')', '; ' order by delivery_form) as treatment_pretty_tg
  from ingredients
  group by treatment_code
)
select
  b.experiment_date,
  b.experiment_name,
  b.roi_code,
  b.roi_path,
  b.clutch_code,
  b.treated_clutch_code,
  b.treatment_code,
  b.treatment_text,
  b.genotype_basecodes,
  b.genotype_pretty,
  b.marker_rollup_display_tg,
  b.marker_rollup_display_fluortag,
  b.marker_rollup_display_fluororganelle,
  b.created_at,
  b.plate_code,
  b.slot_index,
  b.slot_label,
  b.roi_index_within_slot,
  b.roi_note_anatomy,
  b.plate_note,
  b.slot_note,

  coalesce(tp.treatment_pretty_tg, b.treatment_text, ''::text) as treatment_pretty_tg,
  coalesce(tp.treatment_pretty_fluortag, b.treatment_text, ''::text) as treatment_pretty_fluortag,
  coalesce(tp.treatment_pretty_fluororganelle, b.treatment_text, ''::text) as treatment_pretty_fluororganelle,

  case
    when coalesce(btrim(coalesce(tp.treatment_pretty_tg, b.treatment_text)), '') <> '' then
      coalesce(tp.treatment_pretty_tg, b.treatment_text) || ' > ' ||
      coalesce(nullif(btrim(b.marker_rollup_display_tg), ''), nullif(btrim(b.genotype_pretty), ''), '')
    else
      coalesce(nullif(btrim(b.marker_rollup_display_tg), ''), nullif(btrim(b.genotype_pretty), ''), '')
  end as tx_gt_tg,

  case
    when coalesce(btrim(coalesce(tp.treatment_pretty_fluortag, b.treatment_text)), '') <> '' then
      coalesce(tp.treatment_pretty_fluortag, b.treatment_text) || ' > ' ||
      coalesce(nullif(btrim(b.marker_rollup_display_fluortag), ''), nullif(btrim(b.genotype_pretty), ''), '')
    else
      coalesce(nullif(btrim(b.marker_rollup_display_fluortag), ''), nullif(btrim(b.genotype_pretty), ''), '')
  end as tx_gt_fluortag,

  case
    when coalesce(btrim(coalesce(tp.treatment_pretty_fluororganelle, b.treatment_text)), '') <> '' then
      coalesce(tp.treatment_pretty_fluororganelle, b.treatment_text) || ' > ' ||
      coalesce(nullif(btrim(b.marker_rollup_display_fluororganelle), ''), nullif(btrim(b.genotype_pretty), ''), '')
    else
      coalesce(nullif(btrim(b.marker_rollup_display_fluororganelle), ''), nullif(btrim(b.genotype_pretty), ''), '')
  end as tx_gt_fluororganelle

from base b
left join treatment_pretty tp
  on tp.treatment_code = b.treatment_code;
