-- Fixes embedded spaces in fish_code
UPDATE fish
SET fish_code = REPLACE(fish_code, ' ', '')
WHERE fish_code ILIKE '% %';
