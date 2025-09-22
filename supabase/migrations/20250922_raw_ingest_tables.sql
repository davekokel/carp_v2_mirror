-- Raw landing schema (safe to re-run)
create schema if not exists raw;

-- 01_fish.csv
create table if not exists raw.fish_csv (
  fish_name              text,
  mother                 text,
  date_of_birth          text,
  status                 text,
  strain                 text,
  alive                  text,
  breeding_pairing       text,
  fish_code              text,
  archived               text,
  died                   text,
  who                    text
);

-- 10_fish_links_has_transgenes.csv
create table if not exists raw.fish_links_has_transgenes_csv (
  fish_name       text,
  transgene_name  text,
  allele_name     text,
  zygosity        text,
  new_allele_note text
);

-- 10_fish_links_has_treatment_dye.csv
create table if not exists raw.fish_links_has_treatment_dye_csv (
  fish_name   text,
  dye_name    text,
  operator    text,
  performed_at text,
  description text,
  notes       text
);

-- 10_fish_links_has_treatment_injected_plasmid.csv
create table if not exists raw.fish_links_has_treatment_injected_plasmid_csv (
  fish_name      text,
  plasmid_name   text,
  operator       text,
  performed_at   text,
  batch_label    text,
  injection_mix  text,
  injection_notes text,
  enzyme         text
);

-- 10_fish_links_has_treatment_injected_rna.csv
create table if not exists raw.fish_links_has_treatment_injected_rna_csv (
  fish_name   text,
  rna_name    text,
  operator    text,
  performed_at text,
  description text,
  notes       text
);
