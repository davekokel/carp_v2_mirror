ALTER TABLE public.join_fish_fluorescent_treatments VALIDATE CONSTRAINT fk_jfft_ft_code__treatments_fluorescent;
ALTER TABLE public.ft_dyes                      VALIDATE CONSTRAINT fk_ft_dyes_ft_code__treatments_fluorescent;
ALTER TABLE public.ft_dyes                      VALIDATE CONSTRAINT fk_ft_dyes_dye_code__dyes;
ALTER TABLE public.ft_proteins                  VALIDATE CONSTRAINT fk_ft_proteins_ft_code__treatments_fluorescent;
ALTER TABLE public.ft_proteins                  VALIDATE CONSTRAINT fk_ft_proteins_fluor_code__fluors;
ALTER TABLE public.ft_proteins                  VALIDATE CONSTRAINT fk_ft_proteins_tag_code__tags;
ALTER TABLE public.join_fish_transgene_alleles  VALIDATE CONSTRAINT fk_jftga_base_allele__transgene_alleles;
