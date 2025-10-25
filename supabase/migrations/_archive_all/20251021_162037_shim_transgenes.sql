begin;
create table if not exists public.transgenes (
  transgene_base_code text primary key,
  created_at timestamptz default now()
);
commit;
