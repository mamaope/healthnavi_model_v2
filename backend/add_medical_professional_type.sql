-- Migration script to add medical_professional_type column to users table
-- Run this directly in your database if Alembic migration doesn't work

-- Check if column exists before adding (PostgreSQL)
DO $$
BEGIN
    IF NOT EXISTS (
        SELECT 1 
        FROM information_schema.columns 
        WHERE table_name = 'users' 
        AND column_name = 'medical_professional_type'
    ) THEN
        ALTER TABLE users ADD COLUMN medical_professional_type VARCHAR(50) NULL;
        RAISE NOTICE 'Column medical_professional_type added to users table';
    ELSE
        RAISE NOTICE 'Column medical_professional_type already exists';
    END IF;
END $$;

