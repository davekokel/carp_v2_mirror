-- Purge unused tables (no DB dependents/FDKs, no code refs)

drop table if exists public.allele_nicknames           RESTRICT;
drop table if exists public.clutch_genotype_options    RESTRICT;
drop table if exists public.clutch_instance_seq        RESTRICT;
drop table if exists public.cross_parent_aliases       RESTRICT;
drop table if exists public.fish_seed_batches          RESTRICT;
drop table if exists public.fish_year_counters         RESTRICT;
drop table if exists public.injected_plasmid_treatments RESTRICT;
drop table if exists public.injected_rna_treatments    RESTRICT;
drop table if exists public.load_log_fish              RESTRICT;
drop table if exists public.migrations_applied         RESTRICT;
drop table if exists public.mount_label_seq_day        RESTRICT;
drop table if exists public.mount_seq                  RESTRICT;
drop table if exists public.selection_labels           RESTRICT;
drop table if exists public.tank_year_counters         RESTRICT;
