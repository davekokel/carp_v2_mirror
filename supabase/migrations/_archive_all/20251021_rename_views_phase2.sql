begin;

create or replace view public.v_fish as
select
  fa.fish_id,
  fa.fish_code,
  fa.name,
  fa.nickname,
  fa.birthday as date_birth,
  fa.genetic_background,
  fa.description,
  fa.notes,
  gr.genotype,
  coalesce(lc.n_living_tanks,0)::int as n_living_tanks,
  fa.created_at,
  fa.updated_at
from public.v_fish_overview_all fa
left join public.v_fish_genotype_rollup gr on gr.fish_code = fa.fish_code
left join public.v_fish_living_tank_counts lc on lc.fish_id = fa.fish_id;

create or replace view public.v_crosses as
select
  c.cross_id,
  c.cross_code,
  c.mom_code,
  c.dad_code,
  coalesce(s.status,'draft') as status,
  c.n_runs,
  c.latest_cross_date,
  c.n_clutches,
  c.n_containers,
  c.created_by,
  c.created_at
from public.v_crosses_concept c
left join public.v_crosses_status s on s.id = c.cross_id;

create or replace view public.v_clutches as
select
  f.clutch_plan_id,
  f.clutch_code,
  f.mom_code,
  f.dad_code,
  f.planned_name      as name,
  f.planned_nickname  as nickname,
  f.mom_genotype,
  f.dad_genotype,
  f.cross_name_pretty,
  f.clutch_name,
  f.clutch_genotype_pretty,
  f.clutch_genotype_canonical,
  f.mom_strain,
  f.dad_strain,
  f.clutch_strain_pretty,
  f.treatments_count,
  f.treatments_pretty,
  f.clutch_birthday   as birthday,
  f.created_by_instance as created_by,
  f.created_at_instance as created_at
from public.v_clutches_overview_final f;

do $$
declare
  renames text[][];
  pair    text[];
  old_name text;
  new_name text;
begin
  renames := array[
    array['v_tanks','v_tanks'],
    array['v_cross_runs','v_cross_runs'],
    array['v_labels_recent','v_labels_recent'],
    array['v_label_rows','v_label_rows'],
    array['v_tank_pairs','v_tank_pairs'],
    array['v_containers','v_containers'],
    array['v_containers_candidates','v_containers_candidates'],
    array['v_bruker_mounts_enriched','v_bruker_mounts_enriched'],
    array['v_clutches_concept_overview','v_clutches_concept_overview'],
    array['v_clutches_overview_human','v_clutches_overview_human'],
    array['v_crosses_concept','v_crosses_concept'],
    array['v_fish_overview_with_label','v_fish_overview_with_label'],
    array['v_fish_standard','v_fish_standard'],
    array['v_planned_clutches_overview','v_planned_clutches_overview'],
    array['v_plasmids','v_plasmids']
  ];

  foreach pair slice 1 in array renames loop
    old_name := pair[1];
    new_name := pair[2];

    if to_regclass('public.'||old_name) is not null then
      if to_regclass('public.'||new_name) is null then
        execute format('alter view public.%I rename to %I;', old_name, new_name);
      else
        -- target already exists; no shim, just drop the old alias name if it still exists separately
        -- if it’s the same object (already renamed), this will be skipped
        if old_name <> new_name then
          begin
            execute format('drop view if exists public.%I;', old_name);
          exception when undefined_object then
            null;
          end;
        end if;
      end if;
    end if;
  end loop;
end $$;

commit;
