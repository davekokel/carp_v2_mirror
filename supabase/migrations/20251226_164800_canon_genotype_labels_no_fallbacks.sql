-- Keep existing v11_genotype_label_star column names/order intact.
-- Add tg_style_canon as an appended column.

create or replace view public.v11_genotype_label_star as
with g as (
  select
    gv.id as genotype_v11_id,
    gv.genotype_code,
    gv.genotype_pretty,
    gv.genotype_basecodes
  from public.genotypes_v11 gv
),
tokens_raw as (
  select
    g.genotype_v11_id,
    lower(btrim(tok.tok)) as tok
  from g
  cross join lateral regexp_split_to_table(coalesce(g.genotype_basecodes, ''), '[,;|[:space:]]+') tok(tok)
  where nullif(btrim(tok.tok), '') is not null
),
tokens_norm as (
  select
    tr.genotype_v11_id,
    case
      when (regexp_match(regexp_replace(tr.tok, '[^a-z0-9\-]+', '', 'g'), '^([a-z]+)-?0*([0-9]+)$')) is not null then
        format(
          '%s-%s',
          (regexp_match(regexp_replace(tr.tok, '[^a-z0-9\-]+', '', 'g'), '^([a-z]+)-?0*([0-9]+)$'))[1],
          ((regexp_match(regexp_replace(tr.tok, '[^a-z0-9\-]+', '', 'g'), '^([a-z]+)-?0*([0-9]+)$'))[2])::int
        )
      else
        regexp_replace(tr.tok, '[^a-z0-9\-]+', '', 'g')
    end as base_code_norm
  from tokens_raw tr
),
tokens_sort as (
  select
    tn.genotype_v11_id,
    tn.base_code_norm,
    case when tn.base_code_norm ~ '^[a-z]+-[0-9]+$' then 0 else 1 end as sort_kind,
    coalesce((regexp_match(tn.base_code_norm, '^([a-z]+)-([0-9]+)$'))[1], tn.base_code_norm) as sort_prefix,
    coalesce(nullif((regexp_match(tn.base_code_norm, '^([a-z]+)-([0-9]+)$'))[2], '')::int, 0) as sort_num
  from tokens_norm tn
  where nullif(btrim(tn.base_code_norm), '') is not null
),
tokens_sort_distinct as (
  select distinct
    genotype_v11_id,
    base_code_norm,
    sort_kind,
    sort_prefix,
    sort_num
  from tokens_sort
),
g_constructs as (
  select distinct
    ts.genotype_v11_id,
    c.id as construct_id
  from tokens_sort_distinct ts
  join public.constructs c on lower(c.base_code) = ts.base_code_norm
),
fusion_bits as (
  select
    gc.genotype_v11_id,
    coalesce(fl.nickname, fl.display_name, fl.code) as fluor_label,
    coalesce(tg.nickname, tg.display_name, tg.code) as tag_label,
    tg.localization,
    f.tag_pos,
    case
      when tg.id is null then coalesce(fl.nickname, fl.display_name, fl.code)
      else format('%s-%s(%s)', coalesce(fl.nickname, fl.display_name, fl.code), coalesce(tg.nickname, tg.display_name, tg.code), f.tag_pos)
    end as fluor_tag_label,
    case
      when tg.localization is null or tg.localization = '' then coalesce(fl.nickname, fl.display_name, fl.code)
      else format('%s-%s', coalesce(fl.nickname, fl.display_name, fl.code), tg.localization)
    end as organelle_fluor_label
  from g_constructs gc
  join public.construct_fusions cf on cf.construct_id = gc.construct_id
  join public.fusions f on f.id = cf.fusion_id
  join public.fluors fl on fl.id = f.fluor_id
  left join public.tags tg on tg.id = f.tag_id
),
fluor_tag_rollup as (
  select
    fb.genotype_v11_id,
    string_agg(distinct fb.fluor_tag_label, '; ' order by fb.fluor_tag_label) as all_fluor_tag_rollup
  from fusion_bits fb
  group by fb.genotype_v11_id
),
organelle_fluor_rollup as (
  select
    fb.genotype_v11_id,
    string_agg(distinct fb.organelle_fluor_label, '; ' order by fb.organelle_fluor_label) as all_organelle_fluor_rollup
  from fusion_bits fb
  group by fb.genotype_v11_id
),
tg_label_canon as (
  select
    d.genotype_v11_id,
    nullif(
      string_agg(format('tg %s', d.base_code_norm), '; ' order by d.sort_kind, d.sort_prefix, d.sort_num, d.base_code_norm),
      ''
    ) as tg_style_canon
  from tokens_sort_distinct d
  group by d.genotype_v11_id
)
select
  g.genotype_v11_id,
  g.genotype_code,
  g.genotype_pretty,
  g.genotype_basecodes,
  nullif(btrim(ft.all_fluor_tag_rollup), '') as fluor_tag_style,
  nullif(btrim(ofr.all_organelle_fluor_rollup), '') as fluor_organelle_style,
  tlc.tg_style_canon
from g
left join fluor_tag_rollup ft on ft.genotype_v11_id = g.genotype_v11_id
left join organelle_fluor_rollup ofr on ofr.genotype_v11_id = g.genotype_v11_id
left join tg_label_canon tlc on tlc.genotype_v11_id = g.genotype_v11_id
;

create or replace view public.v11_roi_treatment_table_display as
with base as (
  select
    ps.experiment_date,
    ps.experiment_name,
    ps.plate_note,
    ps.slot_note,
    ps.slot_orientation,
    ra.id as roi_id,
    ra.slot_id,
    ra.roi_code,
    ra.roi_index_within_slot,
    ra.roi_note_anatomy,
    ra.roi_path,
    ps.clutch_code,
    m.treated_clutch_id,
    tg.treated_clutch_code,
    ps.treat_code as treatment_code,
    ps.treat_text as treatment_text,
    nullif(btrim(tg.treatment_label_tg_style), '') as tg_style,
    nullif(btrim(tg.treatment_label_fluortag_style), '') as ft_style,
    nullif(btrim(tg.treatment_label_fluororganelle_style), '') as fo_style
  from public.imaging_roi_annotations ra
  left join public.v11_imaging_plate_slot_overview ps on ps.slot_id::uuid = ra.slot_id
  left join public.imaging_clutch_memberships m on m.slot_id = ra.slot_id
  left join public.v11_treated_clutch_genotype_star_labels tg on tg.treated_clutch_id = m.treated_clutch_id
),
clean as (
  select
    b.*,
    nullif(btrim(regexp_replace(coalesce(b.tg_style, ''), '^.*>[[:space:]]*', '')), '') as tg_label,
    nullif(btrim(regexp_replace(coalesce(b.ft_style, ''), '^[[:space:]]*>[[:space:]]*', '')), '') as fluortag_label,
    nullif(btrim(regexp_replace(coalesce(b.fo_style, ''), '^[[:space:]]*>[[:space:]]*', '')), '') as fluororganelle_label_raw,
    (regexp_match(coalesce(b.treatment_text, ''), '(?i)(?:^|\\|)plasmids?=([^|]*)'))[1] as plasmids_raw,
    (regexp_match(coalesce(b.treatment_text, ''), '(?i)(?:^|\\|)rnas?=([^|]*)'))[1] as rnas_raw,
    (regexp_match(coalesce(b.treatment_text, ''), '(?i)(?:^|\\|)dyes?=([^|]*)'))[1] as dyes_raw
  from base b
),
fmt as (
  select
    c.*,
    nullif(btrim(split_part(coalesce(c.fluororganelle_label_raw, ''), '>', 1)), '') as fluororganelle_name,
    nullif(btrim(split_part(coalesce(c.fluororganelle_label_raw, ''), '>', 2)), '') as fluororganelle_basecodes,
    nullif(btrim(c.plasmids_raw), '') as plasmids_basecodes,
    nullif(btrim(c.rnas_raw), '') as rnas_basecodes,
    nullif(btrim(c.dyes_raw), '') as dyes_codes,
    case
      when nullif(btrim(c.plasmids_raw), '') is null then null
      else ('plasmid(' || regexp_replace(btrim(c.plasmids_raw), '\s*[;,]\s*|\s+', '), plasmid(', 'g') || ')')
    end as plasmids_display,
    case
      when nullif(btrim(c.rnas_raw), '') is null then null
      else ('rna(' || regexp_replace(btrim(c.rnas_raw), '\s*[;,]\s*|\s+', '), rna(', 'g') || ')')
    end as rnas_display,
    case
      when nullif(btrim(c.dyes_raw), '') is null then null
      else ('dye(' || regexp_replace(btrim(c.dyes_raw), '\s*[;,]\s*|\s+', '), dye(', 'g') || ')')
    end as dyes_display
  from clean c
),
labels as (
  select
    f1.roi_id,
    f1.roi_code,
    f1.roi_path,
    gls.tg_style_canon as tx_gt_tg,
    gls.fluor_tag_style as gt_fluortag,
    gls.fluor_organelle_style as gt_organelle,
    case
      when nullif(btrim(coalesce(tls.fluor_tag_style, '')), '') is null then null
      when tls.treatment_display ~~* 'rna(%' and tls.treatment_display !~~* '%plasmid(%' then ('rna(' || tls.fluor_tag_style || ')')
      when tls.treatment_display ~~* 'plasmid(%' and tls.treatment_display !~~* '%rna(%' then ('plasmid(' || tls.fluor_tag_style || ')')
      else tls.fluor_tag_style
    end as treat_fluortag_disp,
    case
      when nullif(btrim(coalesce(tls.fluor_organelle_style, '')), '') is null then null
      when tls.treatment_display ~~* 'rna(%' and tls.treatment_display !~~* '%plasmid(%' then ('rna(' || tls.fluor_organelle_style || ')')
      when tls.treatment_display ~~* 'plasmid(%' and tls.treatment_display !~~* '%rna(%' then ('plasmid(' || tls.fluor_organelle_style || ')')
      else tls.fluor_organelle_style
    end as treat_organelle_disp
  from fmt f1
  left join public.clutches c on c.clutch_code = f1.clutch_code
  left join public.v11_genotype_label_star gls on gls.genotype_v11_id = c.genotype_v11_id
  left join public.treated_clutches_v11 tc on tc.treated_clutch_code = f1.treated_clutch_code
  left join public.v11_treatment_label_star tls on tls.treatment_id::uuid = tc.treatment_id
),
labels2 as (
  select
    labels.roi_id,
    labels.tx_gt_tg,
    nullif(btrim(coalesce(labels.treat_fluortag_disp, '')), '') as treat_fluortag_norm,
    nullif(btrim(coalesce(labels.gt_fluortag, '')), '') as gt_fluortag_norm,
    nullif(btrim(coalesce(labels.treat_organelle_disp, '')), '') as treat_organelle_norm,
    nullif(btrim(coalesce(labels.gt_organelle, '')), '') as gt_organelle_norm
  from labels
)
select
  f.experiment_date,
  f.experiment_name,
  f.plate_note,
  f.slot_note,
  f.slot_orientation,
  f.roi_id,
  f.slot_id,
  f.roi_code,
  f.roi_index_within_slot,
  f.roi_note_anatomy,
  f.roi_path,
  f.clutch_code,
  f.treated_clutch_id,
  f.treated_clutch_code,
  f.treatment_code,
  f.treatment_text,
  f.tg_label,
  f.fluortag_label,
  f.fluororganelle_name,
  f.fluororganelle_basecodes,
  f.plasmids_basecodes,
  f.rnas_basecodes,
  f.dyes_codes,
  f.plasmids_display,
  f.rnas_display,
  f.dyes_display,
  l2.tx_gt_tg,
  case
    when coalesce(nullif(btrim(coalesce(l2.treat_fluortag_norm, '')), ''), null) is null
     and coalesce(nullif(btrim(coalesce(l2.gt_fluortag_norm, '')), ''), null) is null then null
    when coalesce(nullif(btrim(coalesce(l2.treat_fluortag_norm, '')), ''), null) is null then l2.gt_fluortag_norm
    when coalesce(nullif(btrim(coalesce(l2.gt_fluortag_norm, '')), ''), null) is null then l2.treat_fluortag_norm
    else (l2.treat_fluortag_norm || ' > ' || l2.gt_fluortag_norm)
  end as tx_gt_fluortag,
  case
    when coalesce(nullif(btrim(coalesce(l2.treat_organelle_norm, '')), ''), null) is null
     and coalesce(nullif(btrim(coalesce(l2.gt_organelle_norm, '')), ''), null) is null then null
    when coalesce(nullif(btrim(coalesce(l2.treat_organelle_norm, '')), ''), null) is null then l2.gt_organelle_norm
    when coalesce(nullif(btrim(coalesce(l2.gt_organelle_norm, '')), ''), null) is null then l2.treat_organelle_norm
    else (l2.treat_organelle_norm || ' > ' || l2.gt_organelle_norm)
  end as tx_gt_fluororganelle
from fmt f
left join labels2 l2 on l2.roi_id = f.roi_id
;
