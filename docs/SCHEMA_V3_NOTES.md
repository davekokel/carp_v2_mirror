# CARP v3 schema notes (tight core)

## Canonical entities & joins
- **clutches** ← renamed from `clutch_instances`
- **treatments** (id, kind_code, name, plasmid_code?, notes)
- **join_clutch_treatments** → FK: (clutch_instance_id → clutches.id, treatment_id → treatments.id), unique (clutch_instance_id, treatment_id)
- **tanks** + **join_fish_tanks** with interval columns `valid_from`, `valid_to` and overlap protections (index + constraint)
- **plasmids**, **fusions**, **join_plasmid_fusions** with validated FKs
- **transgenes**, **transgene_alleles** (PK base+allele), **join_fish_transgene_alleles** with guarded/validated FKs
- **annotations** + **join_annotations** with trigger validation (targets: clutch, mount, mount_slot)

## Views (query-facing)
- `v_clutch_instances_base` → clutches + normalized treatments (no legacy cols)
- `v_clutch_instances` → passthrough to base
- `v_join_clutch_treatments_resolved` → treatment name/code from `treatments`
- `v_fish_tank_history` → intervalized membership
- `v_fish_genotypes_pretty` → compact genotype string
- Labels: `v_labels_for_tanks`, `v_labels_for_crosses` (from jobs/items)
- Annotations: latest + JSON pivots for mounts/slots
- Label history tables replaced by compatibility views

## What we removed / deprecated
- `fish_year_counters` dropped
- `fish_tank_memberships` → removed (compat view was temporary)
- `tank_history` dropped (intervals live in `join_fish_tanks`)
- `join_clutch_treatments.treatment_*` legacy columns removed (now `treatment_id`)

## Invariants
- `join_clutch_treatments`: NOT NULL `treatment_id`, unique `(clutch_instance_id, treatment_id)`
- `join_fish_tanks`: one open interval per fish; no overlaps
- FKs: plasmids⇄fusions, treatments→plasmids(code) (validated), genotype FKs validated

## Next candidates (optional)
- Audit `tank_pairs` usage and either formalize or remove.
- Add GIN on `label_items.payload` if querying by keys is common.
- Centralize “kind_code” enums via check constraints or domain.

