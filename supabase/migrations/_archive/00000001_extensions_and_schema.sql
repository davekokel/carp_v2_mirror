create extension if not exists "uuid-ossp";
create extension if not exists pgcrypto;
grant usage on schema public to anon, authenticated, service_role;
