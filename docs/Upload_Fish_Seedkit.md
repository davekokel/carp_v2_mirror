# Upload Fish Seedkit (Fish + Linking Only)

This page lets collaborators upload **fish rows** and **link transgene alleles**.  
**No injection treatments are ingested from CSV.** Allele numbers are **DB-assigned**.

## Where to find it
Streamlit → “📤 Upload Fish Seedkit”.

## CSV headers (DB-aligned; order not strict)
name,batch_label,line_building_stage,nickname,strain,date_of_birth,description,transgene_base_code,allele_label_legacy,zygosity,created_by

- `name` — required; unique fish name (upsert key)  
- `line_building_stage` — recommended: founder, F0, F1, F2, F3, unknown  
- `date_of_birth` — `YYYY-MM-DD`  
- `transgene_base_code` — optional; base code to link  
- `allele_label_legacy` — optional; legacy label (e.g., “304”)  
- `zygosity` — `heterozygous | homozygous | unknown` (default enforced in DB)  
- **Not in CSV:** `allele_number` — allocated by DB  

## Sample CSV (copy/paste)
```csv
name,batch_label,line_building_stage,nickname,strain,date_of_birth,description,transgene_base_code,allele_label_legacy,zygosity,created_by
mem-tdmSG-13m,seedkit_20251001,founder,membrane-tandem-mStayGold,casper,2025-10-01,import via page,pDQM005,304,unknown,dqm
```

## How to run
1. Open the page → upload your CSV.  
2. Check “Dry run” first. Verify output shows:  
   - `linked 0/1 new allele rows; 1 already existed.` for repeat links, or  
   - `linked 1/1 new allele rows; 0 already existed.` for first-time links.  
3. Uncheck “Dry run” to commit.  

## What success looks like
- Screenshot: page with uploaded preview  
- Screenshot: success output block  

## Quick DB verification (copy/paste)
```sql
select
  f.name,
  fta.transgene_base_code,
  fta.allele_number,           -- DB-assigned
  fta.zygosity
from public.fish f
join public.fish_transgene_alleles fta on f.id = fta.fish_id
where f.name in ('mem-tdmSG-13m','mem-ctrl-01')
order by f.name, fta.transgene_base_code, fta.allele_number;
```

## Guardrails
- CSV must not contain treatment columns; they’re rejected.  
- `allele_number` must not be in CSV; allocator assigns it.  
- Re-runs are idempotent for the same fish + base code (no duplicate links).  

## Troubleshooting
- **Permission denied to table** → ensure you’re using the **write** connection (Streamlit secrets `DB_URL`).  
- **Password failures** → URL-encode the password in `DB_URL`.  
- **Unexpected new allele** → loader now reuses an existing fish↔base_code link before allocating.  
