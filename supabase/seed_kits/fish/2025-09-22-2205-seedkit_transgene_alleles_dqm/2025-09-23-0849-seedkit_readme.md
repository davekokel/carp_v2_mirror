
Here’s a clean, canonical list of the 11 seed-kit CSVs, plus which minimum subsets you need for each scenario.

Full set (11 CSVs)
	1.	01_fish.csv
	2.	02_transgenes.csv
	3.	03_transgene_alleles.csv
	4.	10_links_fish_transgenes.csv
	5.	20_plasmids.csv
	6.	21_plasmid_elements.csv
	7.	30_rnas.csv
	8.	40_treatments_plasmid_injections.csv  (includes an enzyme column as we discussed)
	9.	41_treatments_rna_injections.csv
	10.	42_treatments_dye.csv
	11.	50_links_fish_treatments.csv  (only needed if treatments are modeled as events linked to many fish)

Minimum to upload transgenic fish (4 CSVs)
	•	01_fish.csv
	•	02_transgenes.csv
	•	03_transgene_alleles.csv
	•	10_links_fish_transgenes.csv

Minimum to upload transgenic fish injected with plasmid (6 CSVs)
	•	The 4 above, plus:
	•	20_plasmids.csv
	•	40_treatments_plasmid_injections.csv  (contains fish_name/fish_code, plasmid_code, performed_at, operator, enzyme, etc., so you don’t need a separate link file for this minimal path)