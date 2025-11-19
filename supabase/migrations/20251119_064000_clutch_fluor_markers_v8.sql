BEGIN;

CREATE TABLE IF NOT EXISTS public.clutch_fluor_markers (
  clutch_id     uuid NOT NULL REFERENCES public.clutches(id)
                    ON UPDATE CASCADE ON DELETE CASCADE,
  fluor_id      uuid NOT NULL REFERENCES public.fluors(id)
                    ON UPDATE CASCADE ON DELETE RESTRICT,
  source        text NOT NULL,   -- 'genotype', 'treatment', 'unknown'
  source_detail text,            -- e.g. genotype_code, plasmid_code, RNA code, ROI example
  PRIMARY KEY (clutch_id, fluor_id, source)
);

COMMIT;
