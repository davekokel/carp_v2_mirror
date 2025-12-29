alter table public.legacy_roi_path_map_v5
  add column if not exists orientation text,
  add column if not exists birthday date,
  add column if not exists anatomical_location text;

create or replace view public.v_legacy_roi_path_map_v5_display as
with geno_tok as (
  select
    g.roi_path,
    case
      when coalesce(nullif(btrim(g.allele_code), ''), '') <> '' then
        (('tg(' || g.construct_base_code || ')') || coalesce(nullif(ta.allele_name, ''), '') || '-') || g.allele_code
      else
        'tg(' || g.construct_base_code || ')'
    end as tg_token
  from public.legacy_roi_genotype_constructs_v5 g
  left join public.transgene_alleles ta
    on ta.transgene_base_code = g.construct_base_code
   and ta.allele_nickname = nullif(btrim(g.allele_code), '')
),
geno as (
  select roi_path, string_agg(distinct tg_token, '; ' order by tg_token) as tg_display
  from geno_tok
  group by roi_path
),
ft_tok as (
  select
    g.roi_path,
    case
      when coalesce(nullif(btrim(f.tag_pos), ''), '') <> '' then
        (coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-') || tg.display_name) || '(' || f.tag_pos || ')')
      else
        coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-') || tg.display_name)
    end as fluortag_token
  from public.legacy_roi_genotype_constructs_v5 g
  join public.constructs c on c.base_code = g.construct_base_code
  join public.construct_fusions cf on cf.construct_id = c.id
  join public.fusions f on f.id = cf.fusion_id
  left join public.fluors fl on fl.id = f.fluor_id
  left join public.tags tg on tg.id = f.tag_id
  where coalesce(nullif(btrim(coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-') || tg.display_name)), ''), '') <> ''
),
ft as (
  select roi_path, string_agg(distinct fluortag_token, '; ' order by fluortag_token) as fluortag_display
  from ft_tok
  group by roi_path
),
fo_tok as (
  select
    g.roi_path,
    (fl.display_name || '-') || tg.localization as fluororganelle_token
  from public.legacy_roi_genotype_constructs_v5 g
  join public.constructs c on c.base_code = g.construct_base_code
  join public.construct_fusions cf on cf.construct_id = c.id
  join public.fusions f on f.id = cf.fusion_id
  left join public.fluors fl on fl.id = f.fluor_id
  left join public.tags tg on tg.id = f.tag_id
  where coalesce(nullif(btrim(fl.display_name), ''), '') <> ''
    and coalesce(nullif(btrim(tg.localization), ''), '') <> ''
),
fo as (
  select roi_path, string_agg(distinct fluororganelle_token, '; ' order by fluororganelle_token) as fluororganelle_display
  from fo_tok
  group by roi_path
),
tx_kind as (
  select
    roi_path,
    case when count(distinct kind) = 1 then min(kind) else 'na' end as wrap_kind
  from public.legacy_roi_treatment_constructs_v5
  group by roi_path
),
tx_tg as (
  select
    t.roi_path,
    string_agg(distinct ((k.wrap_kind || '(') || t.construct_base_code) || ')', '; ' order by ((k.wrap_kind || '(') || t.construct_base_code) || ')') as treatment_tg_left
  from public.legacy_roi_treatment_constructs_v5 t
  join tx_kind k using (roi_path)
  group by t.roi_path, k.wrap_kind
),
tx_fo_tok as (
  select
    t.roi_path,
    (fl.display_name || '-') || tg.localization as fo_token
  from public.legacy_roi_treatment_constructs_v5 t
  join public.constructs c on c.base_code = t.construct_base_code
  join public.construct_fusions cf on cf.construct_id = c.id
  join public.fusions f on f.id = cf.fusion_id
  left join public.fluors fl on fl.id = f.fluor_id
  left join public.tags tg on tg.id = f.tag_id
  where coalesce(nullif(btrim(fl.display_name), ''), '') <> ''
    and coalesce(nullif(btrim(tg.localization), ''), '') <> ''
),
tx_fo as (
  select
    x.roi_path,
    string_agg(distinct ((k.wrap_kind || '(') || x.fo_token) || ')', '; ' order by ((k.wrap_kind || '(') || x.fo_token) || ')') as treatment_fo_left
  from tx_fo_tok x
  join tx_kind k using (roi_path)
  group by x.roi_path, k.wrap_kind
),
tx_ft_tok as (
  select
    t.roi_path,
    case
      when coalesce(nullif(btrim(f.tag_pos), ''), '') <> '' then
        (coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-') || tg.display_name) || '(' || f.tag_pos || ')')
      else
        coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-') || tg.display_name)
    end as ft_token
  from public.legacy_roi_treatment_constructs_v5 t
  join public.constructs c on c.base_code = t.construct_base_code
  join public.construct_fusions cf on cf.construct_id = c.id
  join public.fusions f on f.id = cf.fusion_id
  left join public.fluors fl on fl.id = f.fluor_id
  left join public.tags tg on tg.id = f.tag_id
  where coalesce(nullif(btrim(coalesce(nullif(btrim(f.display_name), ''), (fl.display_name || '-') || tg.display_name)), ''), '') <> ''
),
tx_ft as (
  select
    x.roi_path,
    string_agg(distinct ((k.wrap_kind || '(') || x.ft_token) || ')', '; ' order by ((k.wrap_kind || '(') || x.ft_token) || ')') as treatment_ft_left
  from tx_ft_tok x
  join tx_kind k using (roi_path)
  group by x.roi_path, k.wrap_kind
),
tx_any as (
  select
    roi_path,
    string_agg(distinct ((kind || '(') || construct_base_code) || ')', '; ' order by ((kind || '(') || construct_base_code) || ')') as treatment_display
  from public.legacy_roi_treatment_constructs_v5
  group by roi_path
)
select
  m.roi_path,
  case
    when coalesce(nullif(btrim(tx_tg.treatment_tg_left), ''), '') <> '' and coalesce(nullif(btrim(geno.tg_display), ''), '') <> '' then (tx_tg.treatment_tg_left || ' > ') || geno.tg_display
    when coalesce(nullif(btrim(tx_tg.treatment_tg_left), ''), '') <> '' then tx_tg.treatment_tg_left
    else coalesce(geno.tg_display, '')
  end as tg_display,
  case
    when coalesce(nullif(btrim(tx_ft.treatment_ft_left), ''), '') <> '' and coalesce(nullif(btrim(ft.fluortag_display), ''), '') <> '' then (tx_ft.treatment_ft_left || ' > ') || ft.fluortag_display
    when coalesce(nullif(btrim(tx_ft.treatment_ft_left), ''), '') <> '' then tx_ft.treatment_ft_left
    else coalesce(ft.fluortag_display, '')
  end as fluortag_display,
  case
    when coalesce(nullif(btrim(tx_fo.treatment_fo_left), ''), '') <> '' and coalesce(nullif(btrim(fo.fluororganelle_display), ''), '') <> '' then (tx_fo.treatment_fo_left || ' > ') || fo.fluororganelle_display
    when coalesce(nullif(btrim(tx_fo.treatment_fo_left), ''), '') <> '' then tx_fo.treatment_fo_left
    else coalesce(fo.fluororganelle_display, '')
  end as fluororganelle_display,
  coalesce(tx_any.treatment_display, '') as treatment_display,
  m.date_mount_id,
  m.genotype_base_codes,
  m.genotype_allele_codes,
  m.treatment_rna_base_codes,
  m.treatment_plasmid_base_codes,
  m.orientation,
  m.birthday,
  m.anatomical_location
from public.legacy_roi_path_map_v5 m
left join geno using (roi_path)
left join ft using (roi_path)
left join fo using (roi_path)
left join tx_tg using (roi_path)
left join tx_ft using (roi_path)
left join tx_fo using (roi_path)
left join tx_any using (roi_path);
