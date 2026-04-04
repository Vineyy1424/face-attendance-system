-- Migration: 001_teacher_management
-- Purpose: Add teacher profile metadata and ensure default admin account.

CREATE TABLE IF NOT EXISTS teachers (
    teacher_id INT AUTO_INCREMENT PRIMARY KEY,
    username VARCHAR(100) NOT NULL UNIQUE,
    password VARCHAR(255) NOT NULL
);

SET @col_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'teachers'
      AND COLUMN_NAME = 'full_name'
);
SET @sql = IF(
    @col_exists = 0,
    'ALTER TABLE teachers ADD COLUMN full_name VARCHAR(120) NOT NULL DEFAULT ''Teacher''',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'teachers'
      AND COLUMN_NAME = 'created_at'
);
SET @sql = IF(
    @col_exists = 0,
    'ALTER TABLE teachers ADD COLUMN created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

SET @col_exists = (
    SELECT COUNT(*)
    FROM INFORMATION_SCHEMA.COLUMNS
    WHERE TABLE_SCHEMA = DATABASE()
      AND TABLE_NAME = 'teachers'
      AND COLUMN_NAME = 'last_login_at'
);
SET @sql = IF(
    @col_exists = 0,
    'ALTER TABLE teachers ADD COLUMN last_login_at DATETIME NULL',
    'SELECT 1'
);
PREPARE stmt FROM @sql;
EXECUTE stmt;
DEALLOCATE PREPARE stmt;

INSERT INTO teachers (username, password, full_name)
SELECT 'admin', 'admin', 'Administrator'
WHERE NOT EXISTS (
    SELECT 1 FROM teachers WHERE username = 'admin'
);
