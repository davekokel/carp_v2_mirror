# CARP schema checks

## Tables without a PRIMARY KEY

- fish_seed_batches_map

## Foreign keys missing a supporting index

- clutch_containers (container_id) -> containers
- clutch_containers (source_container_id) -> containers
- clutch_plan_treatments (clutch_id) -> clutch_plans
- clutches (cross_instance_id) -> cross_instances
- containers (request_id) -> tank_requests
- cross_instances (cross_id) -> crosses
- cross_instances (father_tank_id) -> containers
- cross_instances (mother_tank_id) -> containers
- cross_plan_genotype_alleles (transgene_base_code, allele_number) -> transgene_alleles
- cross_plan_runs (tank_a_id) -> containers
- cross_plan_runs (tank_b_id) -> containers
- fish_seed_batches (fish_id) -> fish
- fish_transgene_alleles (transgene_base_code, allele_number) -> transgene_alleles
- planned_crosses (cross_id) -> crosses
- planned_crosses (cross_instance_id) -> cross_instances
- planned_crosses (father_tank_id) -> containers
- planned_crosses (mother_tank_id) -> containers
- tank_requests (fish_id) -> fish

## Tables missing created_at or updated_at

- allele_nicknames [missing updated_at]
- clutch_containers [missing updated_at]
- clutch_genotype_options [missing created_at] [missing updated_at]
- clutch_plan_treatments [missing updated_at]
- clutch_plans [missing updated_at]
- clutch_treatments [missing updated_at]
- clutches [missing updated_at]
- container_status_history [missing created_at] [missing updated_at]
- containers [missing updated_at]
- cross_instances [missing updated_at]
- cross_plan_genotype_alleles [missing created_at] [missing updated_at]
- cross_plan_runs [missing updated_at]
- cross_plan_treatments [missing created_at] [missing updated_at]
- cross_plans [missing updated_at]
- crosses [missing updated_at]
- fish [missing updated_at]
- fish_code_audit [missing created_at] [missing updated_at]
- fish_seed_batches [missing created_at]
- fish_seed_batches_map [missing updated_at]
- fish_tank_memberships [missing created_at] [missing updated_at]
- fish_transgene_alleles [missing updated_at]
- fish_year_counters [missing created_at] [missing updated_at]
- injected_plasmid_treatments [missing created_at] [missing updated_at]
- injected_rna_treatments [missing created_at] [missing updated_at]
- label_items [missing created_at] [missing updated_at]
- label_jobs [missing created_at] [missing updated_at]
- load_log_fish [missing created_at] [missing updated_at]
- planned_crosses [missing updated_at]
- plasmid_registry [missing updated_at]
- plasmids [missing updated_at]
- rna_registry [missing updated_at]
- rnas [missing updated_at]
- selection_labels [missing updated_at]
- tank_requests [missing updated_at]
- tank_year_counters [missing created_at] [missing updated_at]
- transgene_allele_counters [missing created_at] [missing updated_at]
- transgene_allele_registry [missing updated_at]
- transgene_alleles [missing created_at] [missing updated_at]
- transgenes [missing updated_at]

## Tables using id_uuid (naming consistency scan)

- clutch_genotype_options
- clutch_plan_treatments
- clutch_plans
- clutch_treatments
- clutches
- containers
- cross_instances
- crosses
- fish
- label_items
- label_jobs
- planned_crosses
- plasmids
- rnas
- selection_labels
- tank_requests
- v_containers_crossing_candidates
- v_containers_live
- v_crosses_status
- v_label_jobs_recent
- vw_fish_standard
- vw_label_rows
- vw_plasmids_overview
