BEGIN;

DROP TABLE IF EXISTS raw.legacy_parent_definitions_v9;

CREATE TABLE raw.legacy_parent_definitions_v9 (
  parent_fish_name     text,
  plasmid_base_code    text,
  allele               text,
  injected_rna         text,
  injected_plasmid     text
);

COMMENT ON TABLE raw.legacy_parent_definitions_v9 IS
'Canonical mapping of legacy parent fish names to plasmid basecodes, allele IDs, and injected RNA/plasmid, from the parent_fish_name → pDQM/MGCO sheet.';

COMMIT;
