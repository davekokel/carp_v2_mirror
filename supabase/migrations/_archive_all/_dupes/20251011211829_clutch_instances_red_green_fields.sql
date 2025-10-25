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
