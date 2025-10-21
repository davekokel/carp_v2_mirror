begin;
alter table public.bruker_mount
  drop column if exists mount_date,
  drop column if exists mount_time,
  drop column if exists mount_notes;
commit;
