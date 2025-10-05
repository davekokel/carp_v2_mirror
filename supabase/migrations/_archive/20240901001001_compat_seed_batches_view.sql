begin;
drop view if exists public.seed_batches cascade;
-- expose BOTH columns so legacy joins work; returns 0 rows
create view public.seed_batches(seed_batch_id, batch_label) as
select null::text as seed_batch_id, null::text as batch_label
where false;
commit;
