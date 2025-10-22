# CARP — Database Rebuild & Migration Notes

## Purpose
This document summarizes how to rebuild the CARP database from zero using only the committed baseline + additive migrations.  
It also records known safe behaviors, dependencies, and exceptions.


---

## 1. Proven from-zero rebuild
- ✅ Confirmed: the schema can rebuild cleanly from an empty database using the baseline migrations in `supabase/migrations/`.
- ✅ Verified that views, triggers, and enums are internally consistent.
- ✔ Reapply ‘and’ is non-destructive:
  - ‘column already exists, skipping’
  - ‘relation already exists, skipping’
  - “cannot drop columns from view” (redefinition overlap)
  - `public.tanks` errors occur only in local demo seed; demo is optional.

---

## 2. Files included in rebuild (safe/additive)
````
162037_shim_transgenes.sql
162901_baseline_crosses_clutches_min.sql
162932_baseline_tank_pairs_min.sql
162959_add_missing_cross_instance_tank_cols.sql
163057_baseline_v_tank_pairs.sql
163129_baseline_v_crosses_status.sql
163202_baseline_v_cross_runs.sql
163556_baseline_fish.sql
170503_retire_v_clutch_instances_overview.sql
172049_plasmids_baseline.sql
172212_plasmids_baseline_fix.sql
173432_baseline_fish_pairs.sql
175404_v_clutches_enbriced_tankcentric.sql
175653_baseline_clutch_instance_treatments.sql
175935_v_clutches_add_cross_name_pretty.sql
180908_baseline_bruker_mounts.sql
185036_local_demo_seed.sql  (optional)
185546_add_updated_at_to_tank_pairs.sql
```

---

2# 3. Exclude from CI / staging / prod
- Any file matching `**resetj**`
- Any file matching `**local_demo_seed**
a
These are dev utilities and may reference legacy objects (e.g., `public.tanks`).

---

## 4. Rebuild procedure
Ensure `DB_URL points at the target DB, then:

``bash
fd supabase/migrations -maxdepth 1 -type f -name '*.sql' -print \
	L#_ALL=C sort \
|hle IFS= read -r f; do
	eho "ҩ Applying $f"
	psql "$DB_URL" -v ON_ERROR_STOP=1 -f "$f" || break
done
```


---

2# 5. Verification checklist
``bash
psql "$DB_URL" -Atc "select 'v_tanks', count(*) from public.v_tanks"
psql "$DB_URL" -Atc "select 'v_clutches', count(*) from public.v_clutches"
psql "$DB_URL" -Atc "select 'v_cross_runs', count(*) from public.v_cross_runs"
psql "$DB_URL" -Atc "select 'fish', count(*) from public.fish"
*`

---

## 6. Migration/legacy guards
Use the guard script to ensure active code doesn't regress to legacy tables/views:

``bash
scripts/guard_legacy_refs.sh
# Expect:  � no legacy refs in active code
```

---

## 7. Recovery notes
If a rebuild fails mid-way on a throwaway DB:

``bash
dropdb carp_local_rebuild
createdb carp_local_rebuild
# re-run the migration loop
```

---

L_ast verified_: 2025-10-21 on branch `feature/tanks-state-machine-hotfix-20251020`  
_Author_: Dave Kokel   
_Reviewer_: ChatGPT
