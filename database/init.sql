-- Content Validation Platform - MySQL Schema
CREATE DATABASE IF NOT EXISTS content_validator CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
USE content_validator;

-- Templates (Batches of approved content)
CREATE TABLE templates (
    id INT AUTO_INCREMENT PRIMARY KEY,
    name VARCHAR(255) NOT NULL UNIQUE,
    description TEXT,
    status ENUM('draft','training','ready','error') DEFAULT 'draft',
    file_count INT DEFAULT 0,
    trained_at DATETIME NULL,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

-- Files within a template
CREATE TABLE template_files (
    id INT AUTO_INCREMENT PRIMARY KEY,
    template_id INT NOT NULL,
    file_name VARCHAR(500) NOT NULL,
    original_name VARCHAR(500) NOT NULL,
    file_type ENUM('image','video') NOT NULL,
    file_path VARCHAR(1000),
    file_url VARCHAR(1000),
    file_size_bytes BIGINT,
    mime_type VARCHAR(100),
    -- LLM-generated summary/description of content
    llm_summary TEXT,
    -- Key visual elements extracted by LLM
    visual_elements JSON,
    -- Color palette extracted
    color_palette JSON,
    -- Text detected in content
    detected_text TEXT,
    -- Embedding vector stored as JSON array
    embedding JSON,
    -- pHash for pixel comparison
    phash VARCHAR(64),
    processing_status ENUM('pending','processing','done','error') DEFAULT 'pending',
    processing_error TEXT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (template_id) REFERENCES templates(id) ON DELETE CASCADE,
    INDEX idx_template_id (template_id),
    INDEX idx_processing_status (processing_status)
);

-- Validation jobs
CREATE TABLE validations (
    id INT AUTO_INCREMENT PRIMARY KEY,
    -- Destination input
    input_type ENUM('upload','url') NOT NULL,
    input_file_name VARCHAR(500),
    input_file_path VARCHAR(1000),
    input_url VARCHAR(2000),
    input_file_type ENUM('image','video') NOT NULL,
    -- Which template was used
    template_id INT NOT NULL,
    template_name VARCHAR(255) NOT NULL,
    -- Metadata captured from URL/post
    post_timestamp DATETIME,
    post_description TEXT,
    post_platform VARCHAR(100),
    -- Overall results
    overall_verdict ENUM('appropriate','escalate','need_review') DEFAULT 'need_review',
    mcc_compliant TINYINT(1) DEFAULT NULL,
    validation_status ENUM('pending','processing','completed','error') DEFAULT 'pending',
    error_message TEXT,
    processing_time_ms INT,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    FOREIGN KEY (template_id) REFERENCES templates(id),
    INDEX idx_template_id (template_id),
    INDEX idx_created_at (created_at),
    INDEX idx_verdict (overall_verdict)
);

-- Per-file match results within a validation
CREATE TABLE validation_matches (
    id INT AUTO_INCREMENT PRIMARY KEY,
    validation_id INT NOT NULL,
    template_file_id INT NOT NULL,
    template_file_name VARCHAR(500) NOT NULL,
    -- Similarity scores
    llm_similarity_score DECIMAL(5,2) DEFAULT 0,
    pixel_similarity_score DECIMAL(5,2) DEFAULT 0,
    semantic_similarity_score DECIMAL(5,2) DEFAULT 0,
    overall_similarity_score DECIMAL(5,2) DEFAULT 0,
    -- Match flags
    is_suspected_match TINYINT(1) DEFAULT 0,
    is_exact_pixel_match TINYINT(1) DEFAULT 0,
    -- LLM reasoning
    match_reasoning TEXT,
    visual_differences TEXT,
    matched_elements JSON,
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (validation_id) REFERENCES validations(id) ON DELETE CASCADE,
    FOREIGN KEY (template_file_id) REFERENCES template_files(id),
    INDEX idx_validation_id (validation_id),
    INDEX idx_similarity (overall_similarity_score)
);

-- Reports log (each validation = one report entry)
CREATE TABLE reports (
    id INT AUTO_INCREMENT PRIMARY KEY,
    validation_id INT NOT NULL UNIQUE,
    report_ref VARCHAR(50) NOT NULL UNIQUE,
    template_name VARCHAR(255),
    input_source VARCHAR(500),
    total_files_compared INT DEFAULT 0,
    suspected_matches INT DEFAULT 0,
    exact_matches INT DEFAULT 0,
    overall_verdict VARCHAR(50),
    mcc_compliant TINYINT(1),
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (validation_id) REFERENCES validations(id),
    INDEX idx_created_at (created_at)
);

-- System settings
CREATE TABLE settings (
    `key` VARCHAR(100) PRIMARY KEY,
    `value` TEXT,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP
);

INSERT INTO settings VALUES 
('llm_provider', 'anthropic', NOW()),
('pixel_match_threshold', '95', NOW()),
('semantic_match_threshold', '75', NOW()),
('mcc_keywords', 'explicit,violent,illegal,harmful,offensive,discriminatory', NOW());
