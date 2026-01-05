-- SQL script to add new fields to chamas_document table
-- Run this in your database to add the missing columns

-- Add file_type column
ALTER TABLE chamas_document ADD COLUMN file_type VARCHAR(10) NULL;

-- Add file_size column  
ALTER TABLE chamas_document ADD COLUMN file_size BIGINT NULL;

-- Update existing records to populate file_type based on file name
UPDATE chamas_document 
SET file_type = LOWER(SUBSTR(file, INSTR(file, '.') + 1))
WHERE file IS NOT NULL AND INSTR(file, '.') > 0;

-- Note: file_size will remain NULL for existing records since we can't retroactively get the size
-- New uploads will have both fields populated automatically