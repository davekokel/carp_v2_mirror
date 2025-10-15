create extension if not exists pgcrypto;

create table if not exists public.clutch_instances (
  id uuid primary key default gen_random_uuid(),
  label text,
  phenotype text,
  notes text,
  red_selected boolean,
  red_intensity text,
  red_note text,
  green_selected boolean,
  green_intensity text,
  green_note text,
  annotated_by text,
  annotated_at timestamptz,
  created_at timestamptz default now()
);

create index if not exists ix_clutch_instances_annotated_at on public.clutch_instances(annotated_at);
create index if not exists ix_clutch_instances_created_at    on public.clutch_instances(created_at);

alter table public.clutch_instances enable row level security;
DO 28762
BEGIN
  if not exists (
    select 1 from pg_policy
    where polrelid='public.clutch_instances'::regclass and polname='app_rw_select_ci_annot'
  ) then
    create policy app_rw_select_ci_annot
      on public.clutch_instances for select to app_rw using (true);
  end if;

  if not exists (
    select 1 from pg_policy
    where polrelid='public.clutch_instances'::regclass and polname='app_rw_update_ci_annot'
  ) then
    create policy app_rw_update_ci_annot
      on public.clutch_instances for update to app_rw using (true) with check (true);
  end if;
end
$$ LANGUAGE plpgsql;
