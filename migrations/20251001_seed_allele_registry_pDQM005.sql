-- 20251001_seed_allele_registry_pDQM005.sql
-- Seed/lock legacy→canonical mapping so alloc() always returns 304 for pDQM005:304
begin;
insert into public.transgene_allele_registry (base_code, legacy_label, allele_number)
values ('pDQM005','304',304)
on conflict (base_code, legacy_label)
do update set allele_number = excluded.allele_number;
commit;
