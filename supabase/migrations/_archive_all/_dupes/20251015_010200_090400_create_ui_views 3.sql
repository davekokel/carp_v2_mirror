SET search_path = public, pg_catalog;

create or replace view public.fish_csv as  SELECT fish_code,
    COALESCE(row_to_json(f.*)::jsonb ->> 'name'::text, ''::text) AS name,
    COALESCE(row_to_json(f.*)::jsonb ->> 'nickname'::text, ''::text) AS nickname,
    COALESCE(row_to_json(f.*)::jsonb ->> 'genetic_background'::text, ''::text) AS genetic_background,
    birthday,
    COALESCE(row_to_json(f.*)::jsonb ->> 'created_by'::text, ''::text) AS created_by,
    created_at
   FROM fish f;;
create or replace view public.seed_batches as  SELECT NULL::text AS seed_batch_id,
    NULL::text AS batch_label
  WHERE false;;
create or replace view public.v_cit_rollup as  SELECT ci.clutch_instance_code,
    count(*)::integer AS treatments_count,
    string_agg((COALESCE(t.material_type, ''::text) || ':'::text) || COALESCE(t.material_code, ''::text), '; '::text ORDER BY t.created_at DESC NULLS LAST) AS treatments_pretty
   FROM clutch_instance_treatments t
     JOIN clutch_instances ci ON ci.id = t.clutch_instance_id
  GROUP BY ci.clutch_instance_code;;
create or replace view public.v_clutch_annotations_summary as  WITH link AS (
         SELECT cl.id AS clutch_id,
            ci.id AS selection_id,
            ci.cross_instance_id,
            ci.created_at,
            ci.annotated_at,
            ci.annotated_by,
            COALESCE(ci.red_selected, false) AS red_selected,
            COALESCE(ci.green_selected, false) AS green_selected,
            NULLIF(btrim(ci.red_intensity), ''::text) AS red_intensity,
            NULLIF(btrim(ci.green_intensity), ''::text) AS green_intensity,
            NULLIF(btrim(ci.notes), ''::text) AS notes,
            NULLIF(btrim(ci.label), ''::text) AS label
           FROM clutches cl
             JOIN cross_instances x ON x.id = cl.cross_instance_id
             JOIN clutch_instances ci ON ci.cross_instance_id = x.id
        ), latest AS (
         SELECT DISTINCT ON (link.clutch_id) link.clutch_id,
            link.selection_id,
            link.cross_instance_id,
            link.created_at,
            link.annotated_at,
            link.annotated_by,
            link.red_selected,
            link.green_selected,
            link.red_intensity,
            link.green_intensity,
            link.notes,
            link.label
           FROM link
          ORDER BY link.clutch_id, (COALESCE(link.annotated_at, link.created_at)) DESC, link.created_at DESC, link.selection_id DESC
        ), annotators AS (
         SELECT s.clutch_id,
            string_agg(s.annotated_by_txt, ', '::text ORDER BY s.annotated_by_txt) AS annotators
           FROM ( SELECT DISTINCT link.clutch_id,
                    COALESCE(link.annotated_by, ''::text) AS annotated_by_txt
                   FROM link
                  WHERE link.annotated_by IS NOT NULL AND btrim(link.annotated_by) <> ''::text) s
          GROUP BY s.clutch_id
        ), agg AS (
         SELECT l.clutch_id,
            count(*)::integer AS annotations_count,
            max(COALESCE(l.annotated_at, l.created_at)) AS last_annotated_at,
            sum(
                CASE
                    WHEN l.red_selected THEN 1
                    ELSE 0
                END)::integer AS red_selected_count,
            sum(
                CASE
                    WHEN l.green_selected THEN 1
                    ELSE 0
                END)::integer AS green_selected_count
           FROM link l
          GROUP BY l.clutch_id
        ), rollup AS (
         SELECT lt.clutch_id,
                CASE
                    WHEN lt.red_selected THEN 'red:'::text || COALESCE(lt.red_intensity, 'selected'::text)
                    ELSE ''::text
                END AS red_part,
                CASE
                    WHEN lt.green_selected THEN 'green:'::text || COALESCE(lt.green_intensity, 'selected'::text)
                    ELSE ''::text
                END AS green_part,
                CASE
                    WHEN lt.notes IS NOT NULL THEN 'note:'::text || "left"(lt.notes, 120)
                    ELSE ''::text
                END AS note_part
           FROM latest lt
        ), rollup_fmt AS (
         SELECT r.clutch_id,
                CASE
                    WHEN NULLIF(r.red_part, ''::text) IS NOT NULL OR NULLIF(r.green_part, ''::text) IS NOT NULL THEN array_to_string(ARRAY[NULLIF(r.red_part, ''::text), NULLIF(r.green_part, ''::text)], ' ; '::text)
                    ELSE ''::text
                END ||
                CASE
                    WHEN NULLIF(r.note_part, ''::text) IS NOT NULL THEN
                    CASE
                        WHEN NULLIF(r.red_part, ''::text) IS NOT NULL OR NULLIF(r.green_part, ''::text) IS NOT NULL THEN ', '::text || r.note_part
                        ELSE r.note_part
                    END
                    ELSE ''::text
                END AS annotation_rollup
           FROM rollup r
        )
 SELECT a.clutch_id,
    COALESCE(a.annotations_count, 0) AS annotations_count,
    a.last_annotated_at,
    COALESCE(n.annotators, ''::text) AS annotators,
    COALESCE(a.red_selected_count, 0) AS red_selected_count,
    COALESCE(a.green_selected_count, 0) AS green_selected_count,
    COALESCE(rf.annotation_rollup, ''::text) AS annotation_rollup
   FROM agg a
     LEFT JOIN annotators n ON n.clutch_id = a.clutch_id
     LEFT JOIN rollup_fmt rf ON rf.clutch_id = a.clutch_id;;
create or replace view public.v_clutch_counts as  WITH runs AS (
         SELECT cp_1.id AS clutch_id,
            cp_1.clutch_code,
            count(DISTINCT ci.id) AS runs_count,
            max(ci.cross_date) AS last_run_date,
            max(ci.clutch_birthday) AS last_birthday
           FROM clutch_plans cp_1
             LEFT JOIN planned_crosses pc ON pc.clutch_id = cp_1.id
             LEFT JOIN cross_instances ci ON ci.cross_id = pc.cross_id
          GROUP BY cp_1.id, cp_1.clutch_code
        ), ann AS (
         SELECT cp_1.id AS clutch_id,
            count(DISTINCT sel.id) AS annotations_count,
            max(sel.annotated_at) AS last_annotated_at
           FROM clutch_plans cp_1
             LEFT JOIN planned_crosses pc ON pc.clutch_id = cp_1.id
             LEFT JOIN cross_instances ci ON ci.cross_id = pc.cross_id
             LEFT JOIN clutch_instances sel ON sel.cross_instance_id = ci.id
          GROUP BY cp_1.id
        )
 SELECT cp.clutch_code,
    COALESCE(r.runs_count, 0::bigint) AS runs_count,
    COALESCE(a.annotations_count, 0::bigint) AS annotations_count,
    r.last_run_date,
    r.last_birthday,
    a.last_annotated_at
   FROM clutch_plans cp
     LEFT JOIN runs r ON r.clutch_id = cp.id
     LEFT JOIN ann a ON a.clutch_id = cp.id;;
create or replace view public.v_clutch_expected_genotype as  SELECT cl.id AS clutch_id,
    COALESCE(cl.expected_genotype, gen_expected_genotype_label(x.mother_code, x.father_code)) AS expected_genotype
   FROM clutches cl
     LEFT JOIN cross_instances ci ON ci.id = cl.cross_instance_id
     LEFT JOIN crosses x ON x.id = ci.cross_id;;
create or replace view public.v_clutch_instance_treatments_effective as  WITH d AS (
         SELECT t.clutch_instance_id,
            lower(COALESCE(t.material_type, ''::text)) AS mt,
            lower(COALESCE(t.material_code, ''::text)) AS mc,
            max(t.created_at) AS last_at
           FROM clutch_instance_treatments t
          GROUP BY t.clutch_instance_id, (lower(COALESCE(t.material_type, ''::text))), (lower(COALESCE(t.material_code, ''::text)))
        )
 SELECT ci.id AS clutch_instance_id,
    count(d.mc)::integer AS treatments_count_effective,
    COALESCE(string_agg(d.mc, ' + '::text ORDER BY d.last_at DESC), ''::text) AS treatments_pretty_effective
   FROM clutch_instances ci
     LEFT JOIN d ON d.clutch_instance_id = ci.id
  GROUP BY ci.id;;
create or replace view public.v_clutch_instances_annotations as  SELECT id,
    COALESCE(label, ''::text) AS label,
    COALESCE(phenotype, ''::text) AS phenotype,
    COALESCE(notes, ''::text) AS notes,
    COALESCE(red_selected, false) AS red_selected,
    COALESCE(red_intensity, ''::text) AS red_intensity,
    COALESCE(red_note, ''::text) AS red_note,
    COALESCE(green_selected, false) AS green_selected,
    COALESCE(green_intensity, ''::text) AS green_intensity,
    COALESCE(green_note, ''::text) AS green_note,
    COALESCE(annotated_by, ''::text) AS annotated_by,
    annotated_at,
    created_at
   FROM clutch_instances;;
create or replace view public.v_clutch_instances_overview as  SELECT ci.id AS cross_instance_id,
    ci.cross_run_code,
    ci.cross_date AS birthday,
    c.clutch_code,
    cl.id AS clutch_instance_id,
    cl.birthday AS clutch_birthday,
    cl.created_by AS clutch_created_by
   FROM cross_instances ci
     LEFT JOIN clutches c ON c.cross_instance_id = ci.id
     LEFT JOIN clutch_instances cl ON cl.cross_instance_id = ci.id;;
create or replace view public.v_clutch_treatments_summary as  WITH base AS (
         SELECT clutch_plan_treatments.clutch_id,
            clutch_plan_treatments.material_type,
            clutch_plan_treatments.material_code,
            COALESCE(NULLIF(btrim(clutch_plan_treatments.material_name), ''::text), clutch_plan_treatments.material_code) AS material_name,
            jsonb_build_object('type', clutch_plan_treatments.material_type, 'code', clutch_plan_treatments.material_code, 'name', COALESCE(NULLIF(btrim(clutch_plan_treatments.material_name), ''::text), clutch_plan_treatments.material_code)) AS obj
           FROM clutch_plan_treatments
        )
 SELECT clutch_id,
    count(*)::integer AS treatments_count,
    string_agg(DISTINCT material_code, ' ; '::text ORDER BY material_code) AS treatments_pretty,
    jsonb_agg(DISTINCT obj ORDER BY obj) AS treatments_json
   FROM base
  GROUP BY clutch_id;;
create or replace view public.v_clutches_overview_effective as  WITH base AS (
         SELECT v_clutches_overview_final_enriched.clutch_plan_id,
            v_clutches_overview_final_enriched.clutch_id,
            v_clutches_overview_final_enriched.clutch_code,
            v_clutches_overview_final_enriched.cross_code,
            v_clutches_overview_final_enriched.cross_name_pretty,
            v_clutches_overview_final_enriched.cross_name,
            v_clutches_overview_final_enriched.clutch_name,
            v_clutches_overview_final_enriched.clutch_nickname,
            v_clutches_overview_final_enriched.clutch_genotype_canonical,
            v_clutches_overview_final_enriched.clutch_genotype_pretty,
            v_clutches_overview_final_enriched.mom_genotype,
            v_clutches_overview_final_enriched.dad_genotype,
            v_clutches_overview_final_enriched.mom_strain,
            v_clutches_overview_final_enriched.dad_strain,
            v_clutches_overview_final_enriched.clutch_strain,
            v_clutches_overview_final_enriched.clutch_strain_pretty,
            v_clutches_overview_final_enriched.treatments_count,
            v_clutches_overview_final_enriched.treatments_pretty,
            v_clutches_overview_final_enriched.treatments_json,
            v_clutches_overview_final_enriched.annotations_count,
            v_clutches_overview_final_enriched.last_annotated_at,
            v_clutches_overview_final_enriched.annotation_rollup,
            v_clutches_overview_final_enriched.clutch_birthday,
            v_clutches_overview_final_enriched.date_planned,
            v_clutches_overview_final_enriched.created_by_plan,
            v_clutches_overview_final_enriched.created_at_plan,
            v_clutches_overview_final_enriched.created_by_instance,
            v_clutches_overview_final_enriched.created_at_instance,
            v_clutches_overview_final_enriched.treatments_count_effective,
            v_clutches_overview_final_enriched.treatments_pretty_effective,
            v_clutches_overview_final_enriched.genotype_treatment_rollup_effective
           FROM v_clutches_overview_final_enriched
        ), ci_norm AS (
         SELECT ci.id,
                CASE
                    WHEN ci.clutch_instance_code ~~ 'CI-%'::text THEN regexp_replace(ci.clutch_instance_code, '-[0-9]{2}$'::text, ''::text)
                    ELSE 'CI-'::text || regexp_replace(ci.clutch_instance_code, '-[0-9]{2}$'::text, ''::text)
                END AS ci_join_code
           FROM clutch_instances ci
        )
 SELECT b.clutch_plan_id,
    b.clutch_id,
    b.clutch_code,
    b.cross_code,
    b.cross_name_pretty,
    b.cross_name,
    b.clutch_name,
    b.clutch_nickname,
    b.clutch_genotype_canonical,
    b.clutch_genotype_pretty,
    b.mom_genotype,
    b.dad_genotype,
    b.mom_strain,
    b.dad_strain,
    b.clutch_strain,
    b.clutch_strain_pretty,
    b.treatments_count,
    b.treatments_pretty,
    b.treatments_json,
    b.annotations_count,
    b.last_annotated_at,
    b.annotation_rollup,
    b.clutch_birthday,
    b.date_planned,
    b.created_by_plan,
    b.created_at_plan,
    b.created_by_instance,
    b.created_at_instance,
    b.treatments_count_effective,
    b.treatments_pretty_effective,
    b.genotype_treatment_rollup_effective,
        CASE
            WHEN v.treatments_count_effective > 0 THEN v.treatments_count_effective
            ELSE b.treatments_count_effective
        END AS treatments_count_effective_eff,
        CASE
            WHEN v.treatments_count_effective > 0 AND COALESCE(v.treatments_pretty_effective, ''::text) <> ''::text THEN v.treatments_pretty_effective
            ELSE b.treatments_pretty_effective
        END AS treatments_pretty_effective_eff,
        CASE
            WHEN v.treatments_count_effective > 0 THEN TRIM(BOTH ' +'::text FROM concat_ws(' + '::text, b.clutch_genotype_pretty, v.treatments_pretty_effective))
            ELSE b.genotype_treatment_rollup_effective
        END AS genotype_treatment_rollup_effective_eff
   FROM base b
     LEFT JOIN ci_norm n ON b.clutch_code = n.ci_join_code
     LEFT JOIN v_clutch_instance_treatments_effective v ON v.clutch_instance_id = n.id;;
create or replace view public.v_clutches_overview_final as  WITH mom AS (
         SELECT v.fish_code,
            string_agg(DISTINCT (v.transgene_base_code || '-'::text) || v.allele_name, ' ; '::text ORDER BY ((v.transgene_base_code || '-'::text) || v.allele_name)) AS canonical,
            string_agg(DISTINCT COALESCE(v.transgene_pretty_name, v.transgene_pretty_nickname, v.transgene_base_code || v.allele_name), ' ; '::text ORDER BY (COALESCE(v.transgene_pretty_name, v.transgene_pretty_nickname, v.transgene_base_code || v.allele_name))) AS pretty,
            max(NULLIF(btrim(v.genetic_background), ''::text)) AS mom_strain
           FROM v_fish_overview_all v
          GROUP BY v.fish_code
        ), dad AS (
         SELECT v.fish_code,
            string_agg(DISTINCT (v.transgene_base_code || '-'::text) || v.allele_name, ' ; '::text ORDER BY ((v.transgene_base_code || '-'::text) || v.allele_name)) AS canonical,
            string_agg(DISTINCT COALESCE(v.transgene_pretty_name, v.transgene_pretty_nickname, v.transgene_base_code || v.allele_name), ' ; '::text ORDER BY (COALESCE(v.transgene_pretty_name, v.transgene_pretty_nickname, v.transgene_base_code || v.allele_name))) AS pretty,
            max(NULLIF(btrim(v.genetic_background), ''::text)) AS dad_strain
           FROM v_fish_overview_all v
          GROUP BY v.fish_code
        ), core AS (
         SELECT cp.id AS clutch_plan_id,
            cl.id AS clutch_id,
            COALESCE(cl.clutch_instance_code, cl.clutch_code, cp.clutch_code, "left"(cl.id::text, 8)) AS clutch_code,
            x.cross_code,
            cl.date_birth AS clutch_birthday,
            cp.cross_date AS date_planned,
            cp.created_by AS created_by_plan,
            cp.created_at AS created_at_plan,
            cl.created_by AS created_by_instance,
            cl.created_at AS created_at_instance,
            x.mother_code,
            x.father_code,
            cp.planned_name,
            cp.planned_nickname
           FROM clutches cl
             JOIN cross_instances ci ON ci.id = cl.cross_instance_id
             JOIN crosses x ON x.id = ci.cross_id
             LEFT JOIN clutch_plans cp ON cp.id = cl.planned_cross_id
        ), joined AS (
         SELECT c.clutch_plan_id,
            c.clutch_id,
            c.clutch_code,
            c.cross_code,
            c.clutch_birthday,
            c.date_planned,
            c.created_by_plan,
            c.created_at_plan,
            c.created_by_instance,
            c.created_at_instance,
            c.mother_code,
            c.father_code,
            c.planned_name,
            c.planned_nickname,
            concat_ws(' × '::text, NULLIF(m.pretty, ''::text), NULLIF(d.pretty, ''::text)) AS cross_name_pretty,
            concat_ws(' × '::text, NULLIF(m.canonical, ''::text), NULLIF(d.canonical, ''::text)) AS cross_name,
            NULLIF(m.pretty, ''::text) AS mom_genotype_raw,
            NULLIF(d.pretty, ''::text) AS dad_genotype_raw,
            COALESCE(m.mom_strain, '(unknown)'::text) AS mom_strain,
            COALESCE(d.dad_strain, '(unknown)'::text) AS dad_strain,
            gu.canonical_union AS clutch_genotype_canonical,
            gu.pretty_union AS clutch_genotype_pretty
           FROM core c
             LEFT JOIN mom m ON m.fish_code = c.mother_code
             LEFT JOIN dad d ON d.fish_code = c.father_code
             LEFT JOIN LATERAL ( WITH toks AS (
                         SELECT unnest(string_to_array(NULLIF(m.canonical, ''::text), ' ; '::text)) AS can,
                            unnest(string_to_array(NULLIF(m.pretty, ''::text), ' ; '::text)) AS pre
                        UNION ALL
                         SELECT unnest(string_to_array(NULLIF(d.canonical, ''::text), ' ; '::text)) AS unnest,
                            unnest(string_to_array(NULLIF(d.pretty, ''::text), ' ; '::text)) AS unnest
                        )
                 SELECT string_agg(DISTINCT toks.can, ' ; '::text ORDER BY toks.can) AS canonical_union,
                    string_agg(DISTINCT toks.pre, ' ; '::text ORDER BY toks.pre) AS pretty_union
                   FROM toks
                  WHERE COALESCE(toks.can, ''::text) <> ''::text AND COALESCE(toks.pre, ''::text) <> ''::text) gu ON true
        )
 SELECT j.clutch_plan_id,
    j.clutch_id,
    j.clutch_code,
    j.cross_code,
    j.cross_name_pretty,
    j.cross_name,
    COALESCE(j.planned_name, j.clutch_genotype_pretty) AS clutch_name,
    COALESCE(j.planned_nickname, COALESCE(j.planned_name, j.clutch_genotype_pretty)) AS clutch_nickname,
    j.clutch_genotype_canonical,
    j.clutch_genotype_pretty,
    COALESCE(j.mom_genotype_raw, j.mother_code) AS mom_genotype,
    COALESCE(j.dad_genotype_raw, j.father_code) AS dad_genotype,
    j.mom_strain,
    j.dad_strain,
    gen_clutch_strain(j.mother_code, j.father_code) AS clutch_strain,
    concat_ws(' × '::text, NULLIF(j.mom_strain, ''::text), NULLIF(j.dad_strain, ''::text)) AS clutch_strain_pretty,
    COALESCE(t.treatments_count, 0) AS treatments_count,
    COALESCE(t.treatments_pretty, ''::text) AS treatments_pretty,
    COALESCE(t.treatments_json, '[]'::jsonb) AS treatments_json,
    COALESCE(a.annotations_count, 0) AS annotations_count,
    a.last_annotated_at,
    COALESCE(a.annotation_rollup, ''::text) AS annotation_rollup,
    j.clutch_birthday,
    j.date_planned,
    j.created_by_plan,
    j.created_at_plan,
    j.created_by_instance,
    j.created_at_instance
   FROM joined j
     LEFT JOIN v_clutch_treatments_summary t ON t.clutch_id = j.clutch_id
     LEFT JOIN v_clutch_annotations_summary a ON a.clutch_id = j.clutch_id;;
create or replace view public.v_clutches_overview_final_enriched as  SELECT base.clutch_plan_id,
    base.clutch_id,
    base.clutch_code,
    base.cross_code,
    base.cross_name_pretty,
    base.cross_name,
    base.clutch_name,
    base.clutch_nickname,
    base.clutch_genotype_canonical,
    base.clutch_genotype_pretty,
    base.mom_genotype,
    base.dad_genotype,
    base.mom_strain,
    base.dad_strain,
    base.clutch_strain,
    base.clutch_strain_pretty,
    base.treatments_count,
    base.treatments_pretty,
    base.treatments_json,
    base.annotations_count,
    base.last_annotated_at,
    base.annotation_rollup,
    base.clutch_birthday,
    base.date_planned,
    base.created_by_plan,
    base.created_at_plan,
    base.created_by_instance,
    base.created_at_instance,
    COALESCE(cit.treatments_count, base.treatments_count) AS treatments_count_effective,
    COALESCE(cit.treatments_pretty, base.treatments_pretty) AS treatments_pretty_effective,
    TRIM(BOTH ' +'::text FROM (COALESCE(base.clutch_genotype_pretty, ''::text) ||
        CASE
            WHEN COALESCE(cit.treatments_pretty, base.treatments_pretty) IS NOT NULL AND COALESCE(cit.treatments_pretty, base.treatments_pretty) <> ''::text THEN ' + '::text
            ELSE ''::text
        END) || COALESCE(cit.treatments_pretty, base.treatments_pretty, ''::text)) AS genotype_treatment_rollup_effective
   FROM v_clutches_overview_final base
     LEFT JOIN v_cit_rollup cit ON cit.clutch_instance_code = base.clutch_code;;
create or replace view public.v_containers_candidates as  SELECT id,
    container_type,
    label,
    status,
    created_by,
    created_at,
    status_changed_at,
    activated_at,
    deactivated_at,
    last_seen_at,
    note
   FROM containers c
  WHERE container_type = ANY (ARRAY['inventory_tank'::text, 'crossing_tank'::text, 'holding_tank'::text, 'nursery_tank'::text, 'petri_dish'::text]);;
create or replace view public.v_containers as  SELECT id,
    container_type,
    label,
    status,
    created_by,
    created_at,
    note,
    request_id,
    status_changed_at,
    activated_at,
    deactivated_at,
    last_seen_at,
    last_seen_source,
    tank_volume_l,
    tank_code
   FROM containers c
  WHERE status = ANY (ARRAY['active'::text, 'new_tank'::text]);;
create or replace view public.v_containers_overview as  SELECT id,
    container_type,
    label,
    tank_code,
    status,
    status_changed_at,
    created_at
   FROM containers c;;
create or replace view public.v_cross_concepts_overview as  SELECT cp.clutch_code AS conceptual_cross_code,
    cp.clutch_name AS name,
    cp.clutch_nickname AS nickname,
    hum.mom_tank_label AS mom_code,
    hum.dad_tank_label AS dad_code,
    hum.mom_tank_label AS mom_code_tank,
    hum.dad_tank_label AS dad_code_tank,
    cp.created_at
   FROM v_clutches_concept_overview cp
     LEFT JOIN v_clutches_overview_human hum ON hum.clutch_code = cp.clutch_code;;
create or replace view public.v_cross_plan_runs_enriched as  SELECT r.id,
    r.plan_id,
    r.seq,
    r.planned_date,
    r.status,
    r.note,
    r.created_by,
    r.created_at,
    p.plan_title,
    p.plan_nickname,
    p.mother_fish_id,
    p.father_fish_id,
    fm.fish_code AS mother_fish_code,
    ff.fish_code AS father_fish_code,
    ca.label AS tank_a_label,
    cb.label AS tank_b_label
   FROM cross_plan_runs r
     JOIN cross_plans p ON p.id = r.plan_id
     LEFT JOIN fish fm ON fm.id = p.mother_fish_id
     LEFT JOIN fish ff ON ff.id = p.father_fish_id
     LEFT JOIN containers ca ON ca.id = r.tank_a_id
     LEFT JOIN containers cb ON cb.id = r.tank_b_id;;
create or replace view public.v_cross_plans_enriched as  SELECT p.id,
    p.plan_date,
    p.status,
    p.created_by,
    p.note,
    p.created_at,
    p.mother_fish_id,
    fm.fish_code AS mother_fish_code,
    p.father_fish_id,
    ff.fish_code AS father_fish_code,
    p.tank_a_id,
    ca.label AS tank_a_label,
    p.tank_b_id,
    cb.label AS tank_b_label,
    COALESCE(( SELECT string_agg(format('%s[%s]%s'::text, g.transgene_base_code, g.allele_number, COALESCE(' '::text || g.zygosity_planned, ''::text)), ', '::text ORDER BY g.transgene_base_code, g.allele_number) AS string_agg
           FROM cross_plan_genotype_alleles g
          WHERE g.plan_id = p.id), ''::text) AS genotype_plan,
    COALESCE(( SELECT string_agg(TRIM(BOTH ' '::text FROM concat(t.treatment_name,
                CASE
                    WHEN t.amount IS NOT NULL THEN ' '::text || t.amount::text
                    ELSE ''::text
                END,
                CASE
                    WHEN t.units IS NOT NULL THEN ' '::text || t.units
                    ELSE ''::text
                END,
                CASE
                    WHEN t.timing_note IS NOT NULL THEN (' ['::text || t.timing_note) || ']'::text
                    ELSE ''::text
                END)), ', '::text ORDER BY t.treatment_name) AS string_agg
           FROM cross_plan_treatments t
          WHERE t.plan_id = p.id), ''::text) AS treatments_plan
   FROM cross_plans p
     LEFT JOIN fish fm ON fm.id = p.mother_fish_id
     LEFT JOIN fish ff ON ff.id = p.father_fish_id
     LEFT JOIN containers ca ON ca.id = p.tank_a_id
     LEFT JOIN containers cb ON cb.id = p.tank_b_id;;
create or replace view public.v_crosses_status as  SELECT id,
    mother_code,
    father_code,
    planned_for,
    created_by,
    created_at,
        CASE
            WHEN (EXISTS ( SELECT 1
               FROM clutches x
              WHERE x.cross_id = c.id)) THEN 'realized'::text
            ELSE 'planned'::text
        END AS status
   FROM crosses c;;
create or replace view public.v_fish_label_fields as  SELECT fish_code,
    nickname,
    name,
    NULL::text AS base_code,
    NULL::text AS tg_nick,
    line_building_stage AS stage,
    date_birth AS dob,
    NULLIF(array_to_string(ARRAY( SELECT (fa2.transgene_base_code || '^'::text) || fa2.allele_number::text
           FROM fish_transgene_alleles fa2
          WHERE fa2.fish_id = f.id
          ORDER BY fa2.transgene_base_code, fa2.allele_number), '; '::text), ''::text) AS genotype,
    genetic_background
   FROM fish f;;
create or replace view public.v_fish_live_counts as  SELECT f.fish_code,
    count(*)::integer AS n_live
   FROM fish f
     JOIN fish_tank_memberships m ON m.fish_id = f.id AND m.left_at IS NULL
     JOIN containers c ON c.id = m.container_id
  WHERE (c.status = ANY (ARRAY['active'::text, 'new_tank'::text])) AND (c.container_type = ANY (ARRAY['inventory_tank'::text, 'holding_tank'::text, 'nursery_tank'::text]))
  GROUP BY f.fish_code;;
create or replace view public.v_fish_living_tank_counts as  SELECT m.fish_id,
    count(*)::integer AS n_living_tanks
   FROM fish_tank_memberships m
     JOIN containers c ON c.id = m.container_id
  WHERE m.left_at IS NULL AND (c.status = ANY (ARRAY['active'::text, 'new_tank'::text]))
  GROUP BY m.fish_id;;
create or replace view public.v_fish_overview as  SELECT fish_code,
    name,
    nickname,
    line_building_stage,
    date_birth,
    genetic_background,
    created_at,
    NULLIF(array_to_string(ARRAY( SELECT (fa2.transgene_base_code || '^'::text) || fa2.allele_number::text
           FROM fish_transgene_alleles fa2
          WHERE fa2.fish_id = f.id
          ORDER BY fa2.transgene_base_code, fa2.allele_number), '; '::text), ''::text) AS genotype_text,
    date_part('day'::text, now() - date_birth::timestamp with time zone)::integer AS age_days
   FROM fish f
  ORDER BY created_at DESC;;
create or replace view public.v_fish_overview_all as  WITH clean0 AS (
         SELECT c.fish_code,
            COALESCE(c.genotype, ''::text) AS genotype,
            COALESCE(c.genetic_background, ''::text) AS genetic_background,
            c.birthday,
            COALESCE(c.transgene_base, ''::text) AS transgene_base,
            c.allele_number,
            COALESCE(c.allele_name, ''::text) AS allele_name,
            COALESCE(c.allele_nickname, ''::text) AS allele_nickname,
            COALESCE(c.transgene_pretty_nickname, ''::text) AS transgene_pretty_nickname,
            COALESCE(c.transgene_pretty_name, ''::text) AS transgene_pretty_name,
            COALESCE(c.genotype_rollup_clean, ''::text) AS genotype_rollup_clean,
            c.created_at,
            COALESCE(c.created_by, ''::text) AS created_by
           FROM v_fish_standard_clean c
        ), linked AS (
         SELECT f.fish_code,
            fta.transgene_base_code AS transgene_base,
            fta.allele_number
           FROM fish_transgene_alleles fta
             JOIN fish f ON f.id = fta.fish_id
        ), clean AS (
         SELECT s.fish_code,
            s.genotype,
            s.genetic_background,
            s.birthday,
            s.transgene_base,
            s.allele_number,
            s.allele_name,
            s.allele_nickname,
            s.transgene_pretty_nickname,
            s.transgene_pretty_name,
            s.genotype_rollup_clean,
            s.created_at,
            s.created_by,
            s.rn
           FROM ( SELECT c0.fish_code,
                    c0.genotype,
                    c0.genetic_background,
                    c0.birthday,
                    c0.transgene_base,
                    c0.allele_number,
                    c0.allele_name,
                    c0.allele_nickname,
                    c0.transgene_pretty_nickname,
                    c0.transgene_pretty_name,
                    c0.genotype_rollup_clean,
                    c0.created_at,
                    c0.created_by,
                    row_number() OVER (PARTITION BY c0.fish_code, c0.transgene_base ORDER BY (
                        CASE
                            WHEN (EXISTS ( SELECT 1
                               FROM linked l
                              WHERE l.fish_code = c0.fish_code AND l.transgene_base = c0.transgene_base AND l.allele_number = c0.allele_number)) THEN 0
                            ELSE 1
                        END), (c0.allele_number IS NULL), c0.allele_number, c0.created_at DESC NULLS LAST) AS rn
                   FROM clean0 c0) s
          WHERE s.rn = 1
        ), fish_meta AS (
         SELECT f.fish_code,
            COALESCE(NULLIF(lv.name, ''::text), NULLIF(f.name, ''::text), ''::text) AS name,
            COALESCE(NULLIF(lv.nickname, ''::text), NULLIF(f.nickname, ''::text), ''::text) AS nickname,
            COALESCE(row_to_json(f.*)::jsonb ->> 'line_building_stage'::text, row_to_json(f.*)::jsonb ->> 'line_building_stage_print'::text, ''::text) AS line_building_stage,
            COALESCE(row_to_json(f.*)::jsonb ->> 'description'::text, ''::text) AS description,
            COALESCE(row_to_json(f.*)::jsonb ->> 'notes'::text, ''::text) AS notes,
            COALESCE(f.created_by, ''::text) AS created_by_fish,
            f.created_at AS created_at_fish
           FROM fish f
             LEFT JOIN v_fish_label_fields lv ON lv.fish_code = f.fish_code
        ), counts AS (
         SELECT v.fish_code,
            v.n_live
           FROM v_fish_live_counts v
        ), zyg AS (
         SELECT f.fish_code,
            fta.transgene_base_code AS transgene_base,
            COALESCE(fta.zygosity, ''::text) AS zygosity
           FROM fish_transgene_alleles fta
             JOIN fish f ON f.id = fta.fish_id
        )
 SELECT COALESCE(cl.fish_code, fm.fish_code) AS fish_code,
    COALESCE(fm.name, ''::text) AS name,
    COALESCE(fm.nickname, ''::text) AS nickname,
    COALESCE(cl.genetic_background, ''::text) AS genetic_background,
    COALESCE(fm.line_building_stage, ''::text) AS line_building_stage,
    COALESCE(fm.description, ''::text) AS description,
    COALESCE(fm.notes, ''::text) AS notes,
    cl.birthday,
    COALESCE(cl.created_by, fm.created_by_fish, ''::text) AS created_by,
    COALESCE(cl.created_at, fm.created_at_fish) AS created_at,
    COALESCE(cl.transgene_base, ''::text) AS transgene_base,
    cl.allele_number,
    COALESCE(cl.allele_name, ''::text) AS allele_name,
    COALESCE(cl.allele_nickname, ''::text) AS allele_nickname,
    COALESCE(z.zygosity, ''::text) AS zygosity,
    COALESCE(cl.transgene_pretty_nickname, ''::text) AS transgene_pretty_nickname,
    COALESCE(cl.transgene_pretty_name, ''::text) AS transgene_pretty_name,
    COALESCE(cl.genotype, ''::text) AS genotype,
    COALESCE(cl.genotype_rollup_clean, ''::text) AS genotype_rollup_clean,
    COALESCE(cl.transgene_base, ''::text) AS transgene_base_code,
    COALESCE(cnt.n_live, 0) AS n_living_tanks
   FROM clean cl
     FULL JOIN fish_meta fm ON fm.fish_code = cl.fish_code
     LEFT JOIN counts cnt ON cnt.fish_code = COALESCE(cl.fish_code, fm.fish_code)
     LEFT JOIN zyg z ON z.fish_code = COALESCE(cl.fish_code, fm.fish_code) AND z.transgene_base = cl.transgene_base
  ORDER BY (COALESCE(cl.fish_code, fm.fish_code));;
create or replace view public.v_fish_overview_canonical as  SELECT fish_code,
    name,
    nickname,
    line_building_stage,
    date_birth,
    genetic_background,
    created_at,
    NULLIF(array_to_string(ARRAY( SELECT (fa2.transgene_base_code || '^'::text) || fa2.allele_number::text
           FROM fish_transgene_alleles fa2
          WHERE fa2.fish_id = f.id
          ORDER BY fa2.transgene_base_code, fa2.allele_number), '; '::text), ''::text) AS genotype_text,
    date_part('day'::text, now() - date_birth::timestamp with time zone)::integer AS age_days,
    ( SELECT m.seed_batch_id
           FROM fish_seed_batches_map m
          WHERE m.fish_id = f.id
          ORDER BY m.logged_at DESC
         LIMIT 1) AS seed_batch_id
   FROM fish f
  ORDER BY created_at DESC;;
create or replace view public.v_fish_overview_human as  WITH open_memberships AS (
         SELECT m.fish_id,
            c.id AS container_id,
            c.tank_code,
            c.label,
            c.status,
            c.created_at
           FROM fish_tank_memberships m
             JOIN containers c ON c.id = m.container_id
          WHERE COALESCE(NULLIF(to_jsonb(m.*) ->> 'left_at'::text, ''::text)::timestamp with time zone, NULLIF(to_jsonb(m.*) ->> 'ended_at'::text, ''::text)::timestamp with time zone) IS NULL AND ((c.status = ANY (ARRAY['active'::text, 'new_tank'::text])) OR c.status IS NULL)
        ), alleles AS (
         SELECT fta.fish_id,
            fta.transgene_base_code AS base_code,
            fta.allele_number,
            COALESCE(ta.allele_nickname, fta.allele_number::text) AS allele_nickname,
            COALESCE(NULLIF(to_jsonb(tg.*) ->> 'transgene_name'::text, ''::text), NULLIF(to_jsonb(tg.*) ->> 'name'::text, ''::text), NULLIF(to_jsonb(tg.*) ->> 'label'::text, ''::text), fta.transgene_base_code) AS transgene_name,
            fta.zygosity
           FROM fish_transgene_alleles fta
             LEFT JOIN transgene_alleles ta ON ta.transgene_base_code = fta.transgene_base_code AND ta.allele_number = fta.allele_number
             LEFT JOIN transgenes tg ON tg.transgene_base_code = fta.transgene_base_code
        ), genotype AS (
         SELECT a.fish_id,
            string_agg(TRIM(BOTH ' '::text FROM (((a.transgene_name || '('::text) || a.allele_number::text) || COALESCE(' '::text || a.zygosity, ''::text)) || ')'::text), ' + '::text ORDER BY a.transgene_name, a.allele_number) AS genotype_rollup,
            min(a.transgene_name) AS transgene_primary,
            min(a.allele_number) AS allele_number_primary,
            min(((a.transgene_name || '('::text) || a.allele_number::text) || ')'::text) AS allele_code_primary
           FROM alleles a
          GROUP BY a.fish_id
        ), current_tank AS (
         SELECT DISTINCT ON (o.fish_id) o.fish_id,
            o.tank_code,
            o.label AS tank_label,
            o.status AS tank_status,
            o.created_at AS tank_created_at
           FROM open_memberships o
          ORDER BY o.fish_id, o.created_at DESC NULLS LAST
        )
 SELECT f.id AS fish_id,
    f.fish_code,
    f.name AS fish_name,
    f.nickname AS fish_nickname,
    f.genetic_background,
    g.allele_number_primary AS allele_number,
    g.allele_code_primary AS allele_code,
    g.transgene_primary AS transgene,
    g.genotype_rollup,
    ct.tank_code,
    ct.tank_label,
    ct.tank_status,
    NULLIF(to_jsonb(f.*) ->> 'stage'::text, ''::text) AS stage,
    f.date_birth,
    f.created_at,
    f.created_by
   FROM fish f
     LEFT JOIN genotype g ON g.fish_id = f.id
     LEFT JOIN current_tank ct ON ct.fish_id = f.id
  ORDER BY f.created_at DESC NULLS LAST;;
create or replace view public.v_fish_search as  SELECT f.fish_code,
    lower((COALESCE(sc.genotype, ''::text) || ' '::text) || COALESCE(sc.genetic_background, ''::text)) AS txt,
    COALESCE(sc.genotype, ''::text) AS genotype,
    COALESCE(sc.genetic_background, ''::text) AS genetic_background,
    COALESCE(l.n_live, 0) AS n_live
   FROM fish f
     LEFT JOIN v_fish_standard_clean sc ON sc.fish_code = f.fish_code
     LEFT JOIN v_fish_live_counts l ON l.fish_code = f.fish_code;;
create or replace view public.v_fish_standard_clean as  WITH vs AS (
         SELECT v_fish_standard.id,
            v_fish_standard.fish_code,
            v_fish_standard.name,
            v_fish_standard.nickname,
            v_fish_standard.genotype,
            v_fish_standard.genetic_background,
            v_fish_standard.stage,
            v_fish_standard.date_birth,
            v_fish_standard.age_days,
            v_fish_standard.created_at,
            v_fish_standard.created_by,
            v_fish_standard.batch_display,
            v_fish_standard.transgene_base_code,
            v_fish_standard.allele_code,
            v_fish_standard.treatments_rollup,
            v_fish_standard.n_living_tanks
           FROM v_fish_standard
        ), src AS (
         SELECT f.fish_code,
            COALESCE(vs.genotype, ''::text) AS genotype,
            COALESCE(vs.genetic_background, ''::text) AS genetic_background,
            vs.date_birth AS birthday,
            COALESCE(to_jsonb(vs.*) ->> 'transgene_base_code'::text, to_jsonb(vs.*) ->> 'transgene'::text, to_jsonb(vs.*) ->> 'transgene_print'::text, ''::text) AS transgene_base,
            f.created_at,
            COALESCE(f.created_by, ''::text) AS created_by,
            COALESCE(f.name, ''::text) AS fish_name_base,
            COALESCE(f.nickname, ''::text) AS fish_nickname_base
           FROM fish f
             LEFT JOIN vs ON vs.fish_code = f.fish_code
        ), joined AS (
         SELECT s.fish_code,
            s.genotype,
            s.genetic_background,
            s.birthday,
            s.transgene_base,
            s.created_at,
            s.created_by,
            s.fish_name_base,
            s.fish_nickname_base,
            l.name AS name_labeled,
            l.nickname AS nickname_labeled
           FROM src s
             LEFT JOIN v_fish_label_fields l ON l.fish_code = s.fish_code
        ), fmt AS (
         SELECT joined.fish_code,
            COALESCE(joined.name_labeled, joined.fish_name_base) AS name,
            COALESCE(joined.nickname_labeled, joined.fish_nickname_base) AS nickname,
            joined.genotype,
            joined.genetic_background,
            joined.birthday,
            joined.transgene_base,
            joined.created_at,
            joined.created_by
           FROM joined
        ), roll AS (
         SELECT f.fish_code,
            f.name,
            f.nickname,
            f.genotype,
            f.genetic_background,
            f.birthday,
            f.transgene_base,
            f.created_at,
            f.created_by,
            ta.allele_nickname,
            ta.allele_number,
            ta.allele_name,
            TRIM(BOTH FROM regexp_replace(concat_ws(' '::text,
                CASE
                    WHEN NULLIF(f.transgene_base, ''::text) IS NOT NULL THEN f.transgene_base ||
                    CASE
                        WHEN ta.allele_number IS NOT NULL THEN ('('::text || ta.allele_number::text) || ')'::text
                        ELSE ''::text
                    END
                    ELSE NULL::text
                END), '\s+'::text, ' '::text, 'g'::text)) AS genotype_rollup_clean
           FROM fmt f
             LEFT JOIN transgene_alleles ta ON ta.transgene_base_code = f.transgene_base
        )
 SELECT fish_code,
    name,
    nickname,
    genotype,
    genetic_background,
    birthday,
    transgene_base,
    allele_number,
    allele_name,
    allele_nickname,
        CASE
            WHEN NULLIF(transgene_base, ''::text) IS NOT NULL AND NULLIF(COALESCE(allele_nickname, ''::text), ''::text) IS NOT NULL THEN (('Tg('::text || transgene_base) || ')'::text) || allele_nickname
            ELSE ''::text
        END AS transgene_pretty_nickname,
        CASE
            WHEN NULLIF(transgene_base, ''::text) IS NOT NULL AND NULLIF(COALESCE(allele_name, ''::text), ''::text) IS NOT NULL THEN (('Tg('::text || transgene_base) || ')'::text) || allele_name
            ELSE ''::text
        END AS transgene_pretty_name,
    genotype_rollup_clean,
    created_at,
    created_by
   FROM roll;;
create or replace view public.v_labels_recent as  SELECT id,
    entity_type,
    entity_id,
    template,
    media,
    status,
    requested_by,
    requested_at,
    started_at,
    finished_at,
    num_labels,
    file_bytes IS NOT NULL OR file_url IS NOT NULL AS has_file
   FROM label_jobs j
  ORDER BY requested_at DESC;;
create or replace view public.v_overview_crosses as  WITH latest_planned AS (
         SELECT DISTINCT ON (cp_1.id) cp_1.id AS clutch_id,
            cp_1.clutch_code,
            cp_1.status,
            pc.id AS planned_id,
            pc.created_at AS planned_created_at,
            pc.cross_id,
            pc.mother_tank_id,
            pc.father_tank_id,
            cp_1.created_at
           FROM clutch_plans cp_1
             LEFT JOIN planned_crosses pc ON pc.clutch_id = cp_1.id
          ORDER BY cp_1.id, pc.created_at DESC NULLS LAST
        ), counts AS (
         SELECT planned_crosses.clutch_id,
            count(*)::integer AS planned_count
           FROM planned_crosses
          GROUP BY planned_crosses.clutch_id
        )
 SELECT lp.clutch_code,
    x.cross_name_code AS name,
    x.cross_name_genotype AS nickname,
    cp.status::text AS status,
    COALESCE(ct.planned_count, 0) AS planned_count,
    x.mother_code AS mom_code,
    x.father_code AS dad_code,
    cm.tank_code AS mom_code_tank,
    cf.tank_code AS dad_code_tank,
    cp.created_at,
    cm.tank_code IS NOT NULL AND cf.tank_code IS NOT NULL AS runnable
   FROM clutch_plans cp
     LEFT JOIN latest_planned lp ON lp.clutch_id = cp.id
     LEFT JOIN counts ct ON ct.clutch_id = cp.id
     LEFT JOIN crosses x ON x.id = lp.cross_id
     LEFT JOIN containers cm ON cm.id = lp.mother_tank_id
     LEFT JOIN containers cf ON cf.id = lp.father_tank_id;;
create or replace view public.v_rna_plasmids as  WITH p AS (
         SELECT p_1.id AS plasmid_id,
            'RNA-'::text || p_1.code AS code,
            p_1.name,
            p_1.nickname,
            p_1.created_at,
            p_1.created_by
           FROM plasmids p_1
          WHERE p_1.supports_invitro_rna = true
        ), pr AS (
         SELECT rr.rna_code AS code,
            NULL::uuid AS plasmid_id,
            rr.rna_nickname AS registry_nickname,
            rr.created_at AS registry_created_at,
            rr.created_by AS registry_created_by
           FROM rna_registry rr
        )
 SELECT COALESCE(p.plasmid_id, pr.plasmid_id) AS plasmid_id,
    COALESCE(p.code, pr.code) AS code,
    COALESCE(p.name, pr.code) AS name,
    COALESCE(pr.registry_nickname, p.nickname, ''::text) AS nickname,
    COALESCE(p.created_at, pr.registry_created_at) AS created_at,
    COALESCE(p.created_by, pr.registry_created_by) AS created_by,
        CASE
            WHEN p.plasmid_id IS NOT NULL THEN 'plasmids'::text
            ELSE 'rna_registry'::text
        END AS source
   FROM p
     FULL JOIN pr ON pr.code = p.code;;
create or replace view public.v_tank_pairs as  SELECT tp.id,
    tp.tank_pair_code,
    tp.concept_id,
    COALESCE(cp.clutch_code, cp.id::text) AS clutch_code,
    tp.status,
    tp.created_by,
    tp.created_at,
    fp.id AS fish_pair_id,
    mf.fish_code AS mom_fish_code,
    df.fish_code AS dad_fish_code,
    tp.mother_tank_id,
    mt.tank_code AS mom_tank_code,
    tp.father_tank_id,
    dt.tank_code AS dad_tank_code
   FROM tank_pairs tp
     JOIN fish_pairs fp ON fp.id = tp.fish_pair_id
     JOIN fish mf ON mf.id = fp.mom_fish_id
     JOIN fish df ON df.id = fp.dad_fish_id
     LEFT JOIN clutch_plans cp ON cp.id = tp.concept_id
     JOIN containers mt ON mt.id = tp.mother_tank_id
     JOIN containers dt ON dt.id = tp.father_tank_id;;
create or replace view public.v_bruker_mounts_enriched as  SELECT mount_code,
    COALESCE(selection_id::text, id::text) AS selection_id,
    mount_date,
    NULL::time without time zone AS mount_time,
    NULL::integer AS n_top,
    NULL::integer AS n_bottom,
    NULL::text AS orientation,
    created_at,
    created_by
   FROM bruker_mounts bm;;
create or replace view public.v_clutches_concept_overview as  WITH base AS (
         SELECT cp.id AS clutch_plan_id,
            pc.id AS planned_cross_id,
            cp.clutch_code,
            cp.planned_name AS clutch_name,
            cp.planned_nickname AS clutch_nickname,
            pc.cross_date AS date_planned,
            COALESCE(cp.note, pc.note) AS note,
            cp.created_by,
            cp.created_at
           FROM clutch_plans cp
             LEFT JOIN planned_crosses pc ON pc.clutch_id = cp.id
        ), inst AS (
         SELECT c.planned_cross_id,
            count(*)::integer AS n_instances,
            max(c.date_birth) AS latest_date_birth,
            count(c.cross_id)::integer AS n_crosses
           FROM clutches c
          GROUP BY c.planned_cross_id
        ), cont AS (
         SELECT c.planned_cross_id,
            count(cc.*)::integer AS n_containers
           FROM clutches c
             JOIN clutch_containers cc ON cc.clutch_id = c.id
          GROUP BY c.planned_cross_id
        )
 SELECT b.clutch_plan_id,
    b.planned_cross_id,
    b.clutch_code,
    b.clutch_name,
    b.clutch_nickname,
    b.date_planned,
    b.created_by,
    b.created_at,
    b.note,
    COALESCE(i.n_instances, 0) AS n_instances,
    COALESCE(COALESCE(i.n_crosses, 0), 0) AS n_crosses,
    COALESCE(ct.n_containers, 0) AS n_containers,
    i.latest_date_birth
   FROM base b
     LEFT JOIN inst i ON i.planned_cross_id = b.planned_cross_id
     LEFT JOIN cont ct ON ct.planned_cross_id = b.planned_cross_id
  ORDER BY (COALESCE(b.date_planned::timestamp without time zone::timestamp with time zone, b.created_at)) DESC NULLS LAST;;
create or replace view public.v_clutches_overview_human as  WITH base AS (
         SELECT c.id AS clutch_id,
            c.date_birth,
            c.created_by,
            c.created_at,
            c.note,
            c.batch_label,
            c.seed_batch_id,
            c.planned_cross_id,
            cp.clutch_code,
            cp.planned_name AS clutch_name,
            COALESCE(mt.label, mt.tank_code) AS mom_tank_label,
            COALESCE(ft.label, ft.tank_code) AS dad_tank_label,
            c.cross_id
           FROM clutches c
             LEFT JOIN planned_crosses pc ON pc.id = c.planned_cross_id
             LEFT JOIN clutch_plans cp ON cp.id = pc.clutch_id
             LEFT JOIN containers mt ON mt.id = pc.mother_tank_id
             LEFT JOIN containers ft ON ft.id = pc.father_tank_id
        ), instances AS (
         SELECT cc.clutch_id,
            count(*)::integer AS n_instances
           FROM clutch_containers cc
          GROUP BY cc.clutch_id
        ), crosses_via_clutches AS (
         SELECT b1.clutch_id,
            count(x.id)::integer AS n_crosses
           FROM base b1
             LEFT JOIN crosses x ON x.id = b1.cross_id
          GROUP BY b1.clutch_id
        )
 SELECT b.clutch_id,
    b.date_birth,
    b.created_by,
    b.created_at,
    b.note,
    b.batch_label,
    b.seed_batch_id,
    b.clutch_code,
    b.clutch_name,
    NULL::text AS clutch_nickname,
    b.mom_tank_label,
    b.dad_tank_label,
    COALESCE(i.n_instances, 0) AS n_instances,
    COALESCE(cx.n_crosses, 0) AS n_crosses
   FROM base b
     LEFT JOIN instances i ON i.clutch_id = b.clutch_id
     LEFT JOIN crosses_via_clutches cx ON cx.clutch_id = b.clutch_id
  ORDER BY (COALESCE(b.date_birth::timestamp with time zone, b.created_at)) DESC NULLS LAST;;
create or replace view public.v_cross_runs as  WITH cl AS (
         SELECT clutches.cross_instance_id,
            count(*)::integer AS n_clutches
           FROM clutches
          GROUP BY clutches.cross_instance_id
        ), cnt AS (
         SELECT c.cross_instance_id,
            count(cc.*)::integer AS n_containers
           FROM clutches c
             JOIN clutch_containers cc ON cc.clutch_id = c.id
          GROUP BY c.cross_instance_id
        )
 SELECT ci.id AS cross_instance_id,
    ci.cross_run_code,
    ci.cross_date,
    x.id AS cross_id,
    COALESCE(x.cross_code, x.id::text) AS cross_code,
    x.mother_code AS mom_code,
    x.father_code AS dad_code,
    cm.label AS mother_tank_label,
    cf.label AS father_tank_label,
    ci.note AS run_note,
    ci.created_by AS run_created_by,
    ci.created_at AS run_created_at,
    COALESCE(cl.n_clutches, 0) AS n_clutches,
    COALESCE(cnt.n_containers, 0) AS n_containers
   FROM cross_instances ci
     JOIN crosses x ON x.id = ci.cross_id
     LEFT JOIN containers cm ON cm.id = ci.mother_tank_id
     LEFT JOIN containers cf ON cf.id = ci.father_tank_id
     LEFT JOIN cl ON cl.cross_instance_id = ci.id
     LEFT JOIN cnt ON cnt.cross_instance_id = ci.id
  ORDER BY ci.cross_date DESC, ci.created_at DESC;;
create or replace view public.v_crosses_concept as  WITH runs AS (
         SELECT cross_instances.cross_id,
            count(*)::integer AS n_runs,
            max(cross_instances.cross_date) AS latest_cross_date
           FROM cross_instances
          GROUP BY cross_instances.cross_id
        ), cl AS (
         SELECT clutches.cross_id,
            count(*)::integer AS n_clutches
           FROM clutches
          GROUP BY clutches.cross_id
        ), cnt AS (
         SELECT c.cross_id,
            count(cc.*)::integer AS n_containers
           FROM clutches c
             JOIN clutch_containers cc ON cc.clutch_id = c.id
          GROUP BY c.cross_id
        )
 SELECT x.id AS cross_id,
    COALESCE(x.cross_code, x.id::text) AS cross_code,
    x.mother_code AS mom_code,
    x.father_code AS dad_code,
    x.created_by,
    x.created_at,
    COALESCE(runs.n_runs, 0) AS n_runs,
    runs.latest_cross_date,
    COALESCE(cl.n_clutches, 0) AS n_clutches,
    COALESCE(cnt.n_containers, 0) AS n_containers
   FROM crosses x
     LEFT JOIN runs ON runs.cross_id = x.id
     LEFT JOIN cl ON cl.cross_id = x.id
     LEFT JOIN cnt ON cnt.cross_id = x.id
  ORDER BY x.created_at DESC;;
create or replace view public.v_fish_overview_with_label as  WITH base AS (
         SELECT f.fish_code,
            f.name,
            f.nickname,
            f.line_building_stage,
            f.date_birth,
            f.genetic_background,
            f.created_by,
            f.created_at
           FROM fish f
        ), allele AS (
         SELECT DISTINCT ON (f2.fish_code) f2.fish_code,
            l.transgene_base_code,
            l.allele_number,
            ta.allele_nickname
           FROM fish_transgene_alleles l
             JOIN fish f2 ON f2.id = l.fish_id
             LEFT JOIN transgene_alleles ta ON ta.transgene_base_code = l.transgene_base_code AND ta.allele_number = l.allele_number
          ORDER BY f2.fish_code, l.transgene_base_code, l.allele_number
        ), batch AS (
         SELECT DISTINCT ON (f3.fish_code) f3.fish_code,
            m.seed_batch_id
           FROM fish_seed_batches_map m
             JOIN fish f3 ON f3.id = m.fish_id
          ORDER BY f3.fish_code, m.logged_at DESC NULLS LAST, m.created_at DESC NULLS LAST
        )
 SELECT b.fish_code,
    b.name,
    b.nickname,
    b.line_building_stage,
    b.date_birth,
    b.genetic_background,
    b.created_by,
    b.created_at,
    a.transgene_base_code AS transgene_base_code_filled,
    a.allele_number::text AS allele_code_filled,
    a.allele_nickname AS allele_name_filled,
    batch.seed_batch_id,
    batch.seed_batch_id AS batch_label,
    COALESCE(b.nickname, ''::text) AS nickname_print,
    COALESCE(b.genetic_background, ''::text) AS genetic_background_print,
    COALESCE(b.line_building_stage, ''::text) AS line_building_stage_print,
    COALESCE(to_char(b.date_birth::timestamp with time zone, 'YYYY-MM-DD'::text), ''::text) AS date_birth_print,
        CASE
            WHEN a.transgene_base_code IS NULL THEN ''::text
            WHEN a.allele_number IS NOT NULL THEN (a.transgene_base_code || '-'::text) || a.allele_number::text
            WHEN a.allele_nickname IS NOT NULL THEN (a.transgene_base_code || ' '::text) || a.allele_nickname
            ELSE a.transgene_base_code
        END AS genotype_print,
        CASE
            WHEN b.date_birth IS NOT NULL THEN CURRENT_DATE - b.date_birth
            ELSE NULL::integer
        END AS age_days,
        CASE
            WHEN b.date_birth IS NOT NULL THEN (CURRENT_DATE - b.date_birth) / 7
            ELSE NULL::integer
        END AS age_weeks,
    COALESCE(b.created_by, ''::text) AS created_by_enriched,
    NULL::text AS plasmid_injections_text,
    NULL::text AS rna_injections_text
   FROM base b
     LEFT JOIN allele a USING (fish_code)
     LEFT JOIN batch USING (fish_code)
  ORDER BY b.fish_code;;
create or replace view public.v_fish_standard as  WITH base AS (
         SELECT f.id,
            f.fish_code,
            COALESCE(f.name, ''::text) AS name,
            COALESCE(f.nickname, ''::text) AS nickname,
            f.date_birth,
            f.created_at,
            COALESCE(f.created_by, ''::text) AS created_by_raw
           FROM fish f
        ), label AS (
         SELECT v.fish_code,
            v.genotype_print AS genotype,
            COALESCE(v.genetic_background_print, v.genetic_background) AS genetic_background,
            COALESCE(v.line_building_stage, v.line_building_stage_print) AS stage,
            v.batch_label,
            v.seed_batch_id,
            v.transgene_base_code_filled AS transgene_base_code,
            v.allele_code_filled AS allele_code,
            v.created_by_enriched,
            NULLIF(v.plasmid_injections_text, ''::text) AS plasmid_injections_text,
            NULLIF(v.rna_injections_text, ''::text) AS rna_injections_text
           FROM v_fish_overview_with_label v
        ), tank_counts AS (
         SELECT m.fish_id,
            count(*)::integer AS n_living_tanks
           FROM fish_tank_memberships m
             JOIN containers c ON c.id = m.container_id
          WHERE m.left_at IS NULL AND c.container_type = 'inventory_tank'::text AND c.deactivated_at IS NULL AND (COALESCE(c.status, ''::text) = ANY (ARRAY['active'::text, 'planned'::text]))
          GROUP BY m.fish_id
        ), roll AS (
         SELECT l1.fish_code,
            TRIM(BOTH '; '::text FROM concat_ws('; '::text,
                CASE
                    WHEN l1.plasmid_injections_text IS NOT NULL THEN 'plasmid: '::text || l1.plasmid_injections_text
                    ELSE NULL::text
                END,
                CASE
                    WHEN l1.rna_injections_text IS NOT NULL THEN 'RNA: '::text || l1.rna_injections_text
                    ELSE NULL::text
                END)) AS treatments_rollup
           FROM label l1
        )
 SELECT b.id,
    b.fish_code,
    b.name,
    b.nickname,
    l.genotype,
    l.genetic_background,
    l.stage,
    b.date_birth,
    CURRENT_DATE - b.date_birth AS age_days,
    b.created_at,
    COALESCE(l.created_by_enriched, b.created_by_raw) AS created_by,
    COALESCE(l.batch_label, l.seed_batch_id) AS batch_display,
    l.transgene_base_code,
    l.allele_code,
    r.treatments_rollup,
    COALESCE(t.n_living_tanks, 0) AS n_living_tanks
   FROM base b
     LEFT JOIN label l USING (fish_code)
     LEFT JOIN roll r USING (fish_code)
     LEFT JOIN tank_counts t ON t.fish_id = b.id;;
create or replace view public.v_label_rows as  WITH base AS (
         SELECT f.id,
            f.fish_code,
            f.name,
            f.nickname,
            f.line_building_stage,
            f.date_birth,
            f.genetic_background,
            f.created_at
           FROM fish f
        ), allele AS (
         SELECT DISTINCT ON (f2.fish_code) f2.fish_code,
            l.transgene_base_code,
            l.allele_number,
            ta.allele_nickname
           FROM fish_transgene_alleles l
             JOIN fish f2 ON f2.id = l.fish_id
             LEFT JOIN transgene_alleles ta ON ta.transgene_base_code = l.transgene_base_code AND ta.allele_number = l.allele_number
          ORDER BY f2.fish_code, l.transgene_base_code, l.allele_number
        ), batch AS (
         SELECT DISTINCT ON (f3.fish_code) f3.fish_code,
            m.seed_batch_id
           FROM fish_seed_batches_map m
             JOIN fish f3 ON f3.id = m.fish_id
          ORDER BY f3.fish_code, m.logged_at DESC NULLS LAST, m.created_at DESC NULLS LAST
        )
 SELECT b.id,
    b.created_at,
    b.fish_code,
    b.name,
    a.transgene_base_code AS transgene_base_code_filled,
    a.allele_number::text AS allele_code_filled,
    a.allele_nickname AS allele_name_filled,
    batch.seed_batch_id AS batch_label,
    COALESCE(b.nickname, ''::text) AS nickname_print,
    COALESCE(b.genetic_background, ''::text) AS genetic_background_print,
    COALESCE(b.line_building_stage, ''::text) AS line_building_stage_print,
    COALESCE(to_char(b.date_birth::timestamp with time zone, 'YYYY-MM-DD'::text), ''::text) AS date_birth_print,
        CASE
            WHEN a.transgene_base_code IS NULL THEN ''::text
            WHEN a.allele_number IS NOT NULL THEN (a.transgene_base_code || '-'::text) || a.allele_number::text
            WHEN a.allele_nickname IS NOT NULL THEN (a.transgene_base_code || ' '::text) || a.allele_nickname
            ELSE a.transgene_base_code
        END AS genotype_print
   FROM base b
     LEFT JOIN allele a USING (fish_code)
     LEFT JOIN batch USING (fish_code)
  ORDER BY b.fish_code;;
create or replace view public.v_planned_clutches_overview as  WITH x AS (
         SELECT cp.id AS clutch_plan_id,
            pc.id AS planned_cross_id,
            cp.clutch_code,
            cp.planned_name AS clutch_name,
            cp.planned_nickname AS clutch_nickname,
            pc.cross_date,
            cp.created_by,
            cp.created_at,
            COALESCE(cp.note, pc.note) AS note
           FROM clutch_plans cp
             LEFT JOIN planned_crosses pc ON pc.clutch_id = cp.id
        ), tx AS (
         SELECT t.clutch_id AS clutch_plan_id,
            count(*)::integer AS n_treatments
           FROM clutch_plan_treatments t
          GROUP BY t.clutch_id
        )
 SELECT x.clutch_plan_id,
    x.planned_cross_id,
    x.clutch_code,
    x.clutch_name,
    x.clutch_nickname,
    x.cross_date,
    x.created_by,
    x.created_at,
    x.note,
    COALESCE(tx.n_treatments, 0) AS n_treatments
   FROM x
     LEFT JOIN tx ON tx.clutch_plan_id = x.clutch_plan_id
  ORDER BY (COALESCE(x.cross_date::timestamp with time zone, x.created_at)) DESC NULLS LAST;;
create or replace view public.v_plasmids as  SELECT p.id,
    p.code,
    p.name,
    p.nickname,
    p.fluors,
    p.resistance,
    p.supports_invitro_rna,
    p.created_by,
    p.notes,
    p.created_at,
    r.id AS rna_id,
    r.code AS rna_code,
    r.name AS rna_name,
    r.source_plasmid_id
   FROM plasmids p
     LEFT JOIN rnas r ON r.source_plasmid_id = p.id
  ORDER BY p.code;;
