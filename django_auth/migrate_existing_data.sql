-- Safe migration script to handle existing data
-- This script adds the created_by column and sets it to the admin user (id=1)

-- 1. Backup existing users just in case
CREATE TABLE IF NOT EXISTS users_backup AS SELECT * FROM users;

-- 2. Add created_by column to validations and reports if they don't exist
-- Using procedure for conditional ALTER to prevent errors

DELIMITER //

CREATE PROCEDURE SafeMigrate()
BEGIN
    -- Add created_by to validations
    IF NOT EXISTS (SELECT * FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'validations' AND COLUMN_NAME = 'created_by') THEN
        ALTER TABLE validations ADD COLUMN created_by INT NULL;
    END IF;

    -- Add created_by to reports
    IF NOT EXISTS (SELECT * FROM information_schema.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'reports' AND COLUMN_NAME = 'created_by') THEN
        ALTER TABLE reports ADD COLUMN created_by INT NULL;
    END IF;

    -- Update existing records to be owned by the first admin (ID=1)
    UPDATE validations SET created_by = 1 WHERE created_by IS NULL;
    UPDATE reports SET created_by = 1 WHERE created_by IS NULL;
    
    -- Add foreign keys
    -- Note: This assumes the new 'users' table is already created by Django and has an ID=1
END //

DELIMITER ;

CALL SafeMigrate();
DROP PROCEDURE SafeMigrate;
