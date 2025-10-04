begin;
-- WARNING: local/dev convenience only. Do NOT run in shared envs.
-- Reset counters and re-map nicknames for this base.

-- 1) delete links that reference this base (optional)
delete from public.fish_transgene_alleles
where transgene_base_code = 'pDQM005';

-- 2) clear registry rows for this base
delete from public.transgene_allele_registry
where transgene_base_code = 'pDQM005';

-- 3) reset counter to 1
insert into public.transgene_allele_counters(transgene_base_code, next_number)
values ('pDQM005', 1)
on conflict (transgene_base_code) do update set next_number = excluded.next_number;

commit;
