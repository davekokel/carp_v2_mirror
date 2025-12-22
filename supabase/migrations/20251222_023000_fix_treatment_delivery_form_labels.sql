create or replace view public.v11_treatment_star as
with mix_constructs as (
  select
    tm.treatment_id,
    tmc.construct_id,
    lower(nullif(btrim(tmc.delivery_form), '')) as delivery_form
  from public.treatment_mixes tm
  join public.treatment_mix_constructs tmc on tmc.mix_id = tm.id
),
base_codes as (
  select
    mc.treatment_id,
    string_agg(distinct c.construct_code, '; ' order by c.construct_code) as genotype_basecode_code
  from mix_constructs mc
  join public.constructs c on c.id = mc.construct_id
  group by mc.treatment_id
),
constructs_by_form as (
  select
    mc.treatment_id,
    mc.delivery_form,
    string_agg(distinct c.construct_code, ', ' order by c.construct_code) as form_codes
  from mix_constructs mc
  join public.constructs c on c.id = mc.construct_id
  where mc.delivery_form is not null
  group by mc.treatment_id, mc.delivery_form
),
dyes_by_treatment as (
  select
    tm.treatment_id,
    string_agg(distinct d.code, ', ' order by d.code) as dye_codes
  from public.treatment_mixes tm
  join public.treatment_mix_dyes tmd on tmd.mix_id = tm.id
  join public.dyes d on d.id = tmd.dye_id
  group by tm.treatment_id
),
materials_by_kind as (
  select
    x.treatment_id,
    string_agg(x.bit, '; ' order by x.ord, x.kind) as materials_by_kind
  from (
    select
      cbf.treatment_id,
      1 as ord,
      cbf.delivery_form as kind,
      format('%s(%s)', cbf.delivery_form, cbf.form_codes) as bit
    from constructs_by_form cbf
    union all
    select
      dyt.treatment_id,
      2 as ord,
      'dye' as kind,
      format('dye(%s)', dyt.dye_codes) as bit
    from dyes_by_treatment dyt
  ) x
  group by x.treatment_id
),
fusion_bits as (
  select
    mc.treatment_id,
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
  from mix_constructs mc
  join public.construct_fusions cf on cf.construct_id = mc.construct_id
  join public.fusions f on f.id = cf.fusion_id
  join public.fluors fl on fl.id = f.fluor_id
  left join public.tags tg on tg.id = f.tag_id
),
fluor_tag_rollup as (
  select
    s.treatment_id,
    string_agg(s.fluor_tag_label, '; ' order by s.fluor_tag_label) as all_fluor_tag_rollup
  from (
    select distinct
      fb.treatment_id,
      fb.fluor_tag_label
    from fusion_bits fb
  ) s
  group by s.treatment_id
),
organelle_fluor_rollup as (
  select
    s.treatment_id,
    string_agg(s.organelle_fluor_label, '; ' order by s.organelle_fluor_label) as all_organelle_fluor_rollup
  from (
    select distinct
      fb.treatment_id,
      fb.organelle_fluor_label
    from fusion_bits fb
  ) s
  group by s.treatment_id
)
select
  t.id::text as treatment_id,
  t.treat_code as treatment_code,
  coalesce(bc.genotype_basecode_code, '') as genotype_basecode_code,
  coalesce(mk.materials_by_kind, '') as materials_by_kind,
  coalesce(ft.all_fluor_tag_rollup, '') as all_fluor_tag_rollup,
  coalesce(ofr.all_organelle_fluor_rollup, '') as all_organelle_fluor_rollup,
  t.kind_code,
  t.treat_text,
  t.created_at
from public.treatments t
left join base_codes bc on bc.treatment_id = t.id
left join materials_by_kind mk on mk.treatment_id = t.id
left join fluor_tag_rollup ft on ft.treatment_id = t.id
left join organelle_fluor_rollup ofr on ofr.treatment_id = t.id
;

create or replace view public.v11_treatment_label_star as
with base as (
  select
    ts.treatment_id,
    ts.treatment_code as treat_code,
    ts.kind_code,
    t.treatment_type,
    t.nickname,
    t.display_name,
    t.treat_text,
    t.notes,
    t.source_system,
    t.import_batch_id,
    t.created_at,
    ts.genotype_basecode_code,
    ts.materials_by_kind,
    ts.all_fluor_tag_rollup,
    ts.all_organelle_fluor_rollup
  from public.v11_treatment_star ts
  join public.treatments t on t.id::text = ts.treatment_id
),
mix_counts as (
  select tm.treatment_id::text as treatment_id, count(*)::integer as n_mixes
  from public.treatment_mixes tm
  group by tm.treatment_id
),
construct_counts as (
  select tm.treatment_id::text as treatment_id, count(distinct tmc.construct_id)::integer as n_constructs
  from public.treatment_mixes tm
  join public.treatment_mix_constructs tmc on tmc.mix_id = tm.id
  group by tm.treatment_id
),
dye_counts as (
  select tm.treatment_id::text as treatment_id, count(distinct tmd.dye_id)::integer as n_dyes
  from public.treatment_mixes tm
  join public.treatment_mix_dyes tmd on tmd.mix_id = tm.id
  group by tm.treatment_id
),
ingredient_kinds as (
  select
    x.treatment_id::text as treatment_id,
    string_agg(distinct x.ingredient_kind, ', ' order by x.ingredient_kind) as ingredient_kinds,
    count(distinct x.ingredient_kind)::integer as n_kinds
  from (
    select
      tm.treatment_id,
      lower(nullif(btrim(tmc.delivery_form), '')) as ingredient_kind
    from public.treatment_mixes tm
    join public.treatment_mix_constructs tmc on tmc.mix_id = tm.id
    where nullif(btrim(tmc.delivery_form), '') is not null
    union all
    select
      tm.treatment_id,
      'dye'::text as ingredient_kind
    from public.treatment_mixes tm
    join public.treatment_mix_dyes tmd on tmd.mix_id = tm.id
  ) x
  group by x.treatment_id
),
inj_markers as (
  select t.id::text as treatment_id, lower(regexp_replace(t.treat_code, '^INJ-', '')) as inj_base_code
  from public.treatments t
  where t.treat_code ~~* 'INJ-%'
),
labelled as (
  select
    b.treatment_id,
    b.treat_code,
    b.kind_code,
    b.treatment_type,
    b.nickname,
    b.display_name,
    b.treat_text,
    b.notes,
    b.source_system,
    b.import_batch_id,
    b.created_at,
    coalesce(m.n_mixes, 0) as n_mixes,
    coalesce(cc.n_constructs, 0) as n_constructs,
    coalesce(dc.n_dyes, 0) as n_dyes,
    coalesce(k.ingredient_kinds, '') as ingredient_kinds,
    coalesce(k.n_kinds, 0) as n_kinds,
    b.genotype_basecode_code,
    b.materials_by_kind,
    nullif(b.all_fluor_tag_rollup, '') as fluor_tag_style,
    nullif(b.all_organelle_fluor_rollup, '') as fluor_organelle_style,
    case
      when nullif(b.materials_by_kind, '') is not null then b.materials_by_kind
      when inj.inj_base_code is not null then 'plasmid(' || inj.inj_base_code || ')'
      else ''
    end as treatment_display
  from base b
  left join mix_counts m on m.treatment_id = b.treatment_id
  left join construct_counts cc on cc.treatment_id = b.treatment_id
  left join dye_counts dc on dc.treatment_id = b.treatment_id
  left join ingredient_kinds k on k.treatment_id = b.treatment_id
  left join inj_markers inj on inj.treatment_id = b.treatment_id
)
select
  treatment_id,
  treat_code,
  kind_code,
  treatment_type,
  nickname,
  display_name,
  treat_text,
  notes,
  source_system,
  import_batch_id,
  created_at,
  n_mixes,
  n_constructs,
  n_dyes,
  ingredient_kinds,
  n_kinds,
  genotype_basecode_code,
  materials_by_kind,
  fluor_tag_style,
  fluor_organelle_style,
  treatment_display
from labelled
;

create or replace view public.v11_roi_flat_table_display as
with base as (
  select
    ps.experiment_date,
    ps.experiment_name,
    ps.plate_note,
    ps.slot_note,
    ps.slot_orientation,
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
    nullif(btrim(tg.treatment_label_fluororganelle_style), '') as fo_style,
    tc.treatment_id as treatment_id
  from public.imaging_roi_annotations ra
  left join public.v11_imaging_plate_slot_overview ps on ps.slot_id::uuid = ra.slot_id
  left join public.imaging_clutch_memberships m on m.slot_id = ra.slot_id
  left join public.treated_clutches_v11 tc on tc.id = m.treated_clutch_id
  left join public.v11_treated_clutch_genotype_star_labels tg on tg.treated_clutch_id = m.treated_clutch_id
),
labels as (
  select
    b.*,
    nullif(btrim(regexp_replace(coalesce(b.tg_style, ''), '^.*>[[:space:]]*', '')), '') as tg_label,
    nullif(btrim(regexp_replace(coalesce(b.ft_style, ''), '^[[:space:]]*>[[:space:]]*', '')), '') as fluortag_label,
    nullif(btrim(regexp_replace(coalesce(b.fo_style, ''), '^[[:space:]]*>[[:space:]]*', '')), '') as fluororganelle_label_raw
  from base b
),
mix_materials as (
  select
    tm.treatment_id,
    string_agg(distinct c.construct_code, '; ' order by c.construct_code) filter (where lower(btrim(tmc.delivery_form))='plasmid') as plasmids_basecodes,
    string_agg(distinct c.construct_code, '; ' order by c.construct_code) filter (where lower(btrim(tmc.delivery_form))='rna') as rnas_basecodes,
    string_agg(distinct d.code, '; ' order by d.code) as dyes_codes
  from public.treatment_mixes tm
  left join public.treatment_mix_constructs tmc on tmc.mix_id = tm.id
  left join public.constructs c on c.id = tmc.construct_id
  left join public.treatment_mix_dyes tmd on tmd.mix_id = tm.id
  left join public.dyes d on d.id = tmd.dye_id
  group by tm.treatment_id
),
fmt as (
  select
    l.roi_path,
    l.roi_note_anatomy,
    l.slot_orientation,
    l.plate_note,
    l.slot_note,
    l.experiment_name,
    l.experiment_date,
    l.roi_code,
    l.roi_index_within_slot,
    l.clutch_code,
    l.treated_clutch_code,
    l.treated_clutch_id,
    l.treatment_code,
    l.treatment_text,
    l.tg_label,
    l.fluortag_label,
    nullif(btrim(split_part(coalesce(l.fluororganelle_label_raw, ''), '>', 1)), '') as fluororganelle_name,
    nullif(btrim(split_part(coalesce(l.fluororganelle_label_raw, ''), '>', 2)), '') as fluororganelle_basecodes,
    nullif(btrim(mm.plasmids_basecodes), '') as plasmids_basecodes,
    nullif(btrim(mm.rnas_basecodes), '') as rnas_basecodes,
    nullif(btrim(mm.dyes_codes), '') as dyes_codes,
    case
      when nullif(btrim(mm.plasmids_basecodes), '') is null then null
      else 'plasmid(' || regexp_replace(btrim(mm.plasmids_basecodes), '\s*[;,]\s*|\s+', '), plasmid(', 'g') || ')'
    end as plasmids_display,
    case
      when nullif(btrim(mm.rnas_basecodes), '') is null then null
      else 'rna(' || regexp_replace(btrim(mm.rnas_basecodes), '\s*[;,]\s*|\s+', '), rna(', 'g') || ')'
    end as rnas_display,
    case
      when nullif(btrim(mm.dyes_codes), '') is null then null
      else 'dye(' || regexp_replace(btrim(mm.dyes_codes), '\s*[;,]\s*|\s+', '), dye(', 'g') || ')'
    end as dyes_display
  from labels l
  left join mix_materials mm on mm.treatment_id = l.treatment_id
)
select
  roi_path,
  roi_note_anatomy,
  slot_orientation,
  plate_note,
  slot_note,
  experiment_name,
  experiment_date,
  roi_code,
  roi_index_within_slot,
  clutch_code,
  treated_clutch_code,
  treated_clutch_id,
  treatment_code,
  treatment_text,
  tg_label,
  fluortag_label,
  fluororganelle_name,
  fluororganelle_basecodes,
  plasmids_basecodes,
  rnas_basecodes,
  dyes_codes,
  plasmids_display,
  rnas_display,
  dyes_display
from fmt
;
