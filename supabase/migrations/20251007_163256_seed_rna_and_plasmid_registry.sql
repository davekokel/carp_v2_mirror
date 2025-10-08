BEGIN;

-- RNAs -----------------------------------------------------------------
INSERT INTO public.rna_registry (rna_code, rna_nickname, vendor, lot_number, notes, created_by)
VALUES
  ('RNA-GFP-001',    'gfp sgRNA #1',         'IDT',     'LOT-A123', 'test sgRNA targeting gfp exon 1',  'seed'),
  ('RNA-p53-001',    'tp53 sgRNA #1',        'IDT',     'LOT-B456', 'tp53 exon 4',                      'seed'),
  ('RNA-p53-002',    'tp53 sgRNA #2',        'IDT',     'LOT-B789', 'tp53 exon 7',                      'seed'),
  ('RNA-CRISPR-CTRL','non-targeting control','IDT',     'LOT-C111', 'negative control',                 'seed'),
  ('RNA-tdTom-001',  'tdTomato sgRNA #1',    'Twist',   'LOT-D222', 'tdTom exon 2',                     'seed')
ON CONFLICT (rna_code) DO NOTHING;

-- Plasmids --------------------------------------------------------------
INSERT INTO public.plasmid_registry (plasmid_code, plasmid_nickname, backbone, insert_desc, vendor, lot_number, notes, created_by)
VALUES
  ('PL-GFP-001',   'GFP expr',      'pCS2+',   'CMV::GFP',                'Addgene', 'LOT-P100', 'general GFP expression',     'seed'),
  ('PL-Cas9-001',  'SpCas9',        'pCS2+',   'CMV::SpCas9-NLS',         'Addgene', 'LOT-P101', 'SpCas9 with NLS',           'seed'),
  ('PL-BaseEdit',  'BE4max',        'pCMV',    'CMV::BE4max',             'Addgene', 'LOT-P102', 'base editor BE4max',         'seed'),
  ('PL-mCherry',   'mCh expr',      'pTol2',   'UAS::mCherry',            'Lab',     'LOT-P103', 'UAS-mCherry transgenesis',   'seed'),
  ('PL-Guide-Vec', 'gRNA vector',   'pU6',     'U6::gRNA scaffold',       'Lab',     'LOT-P104', 'U6-driven gRNA scaffold',    'seed')
ON CONFLICT (plasmid_code) DO NOTHING;

COMMIT;
