alter table public.clutch_instances
  add column if not exists red_selected    boolean,
  add column if not exists red_intensity   text,
  add column if not exists red_note        text,
  add column if not exists green_selected  boolean,
  add column if not exists green_intensity text,
  add column if not exists green_note      text;

alter table public.clutch_instances
  add column if not exists phenotype    text,
  add column if not exists notes        text,
  add column if not exists annotated_by text,
  add column if not exists annotated_at timestamptz;

-- helpful ordering filters
create index if not exists ix_clutch_instances_annotated_at on public.clutch_instances(annotated_at);
create index if not exists ix_clutch_instances_created_at    on public.clutch_instances(created_at);
