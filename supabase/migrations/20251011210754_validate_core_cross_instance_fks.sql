-- All orphan checks returned 0, so validate the constraints
alter table public.cross_instances validate constraint fk_ci_cross;
alter table public.cross_instances validate constraint fk_ci_mother_container;
alter table public.cross_instances validate constraint fk_ci_father_container;
