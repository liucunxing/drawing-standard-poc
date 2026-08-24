SET NAMES utf8mb4;

CREATE TABLE IF NOT EXISTS system_config (
  key_name VARCHAR(100) NOT NULL,
  key_value TEXT NOT NULL,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (key_name)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

INSERT INTO system_config (key_name, key_value) VALUES
  ('tmp_dir', '/app/project/drawing-standard-poc/backend/tmp'),
  ('paddle_models_root', '/app/models/paddlex/official_models')
ON DUPLICATE KEY UPDATE key_value = VALUES(key_value);

CREATE TABLE IF NOT EXISTS pdf_task (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  task_id VARCHAR(255) NOT NULL,
  user_id BIGINT UNSIGNED DEFAULT NULL,
  original_filename VARCHAR(255) NOT NULL,
  file_size BIGINT NOT NULL DEFAULT 0,
  file_path VARCHAR(1000) NOT NULL,
  page_count INT NOT NULL DEFAULT 0,
  status TINYINT NOT NULL DEFAULT 0,
  progress DECIMAL(5,2) NOT NULL DEFAULT 0.00,
  current_step VARCHAR(255) DEFAULT NULL,
  table_count INT NOT NULL DEFAULT 0,
  standard_count INT NOT NULL DEFAULT 0,
  exact_match_count INT NOT NULL DEFAULT 0,
  year_mismatch_count INT NOT NULL DEFAULT 0,
  similar_count INT NOT NULL DEFAULT 0,
  not_found_count INT NOT NULL DEFAULT 0,
  error_message TEXT DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  started_at DATETIME DEFAULT NULL,
  completed_at DATETIME DEFAULT NULL,
  PRIMARY KEY (id),
  UNIQUE KEY uk_pdf_task_task_id (task_id),
  KEY idx_pdf_task_created_at (created_at),
  KEY idx_pdf_task_status (status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS table_image (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  task_id VARCHAR(255) NOT NULL,
  table_index INT NOT NULL,
  page_number INT NOT NULL DEFAULT 0,
  image_filename VARCHAR(255) NOT NULL,
  image_path VARCHAR(1000) NOT NULL,
  image_width INT NOT NULL DEFAULT 0,
  image_height INT NOT NULL DEFAULT 0,
  file_size BIGINT NOT NULL DEFAULT 0,
  dpi INT NOT NULL DEFAULT 300,
  bbox_x INT DEFAULT NULL,
  bbox_y INT DEFAULT NULL,
  bbox_width INT DEFAULT NULL,
  bbox_height INT DEFAULT NULL,
  ocr_status TINYINT NOT NULL DEFAULT 0,
  ocr_error TEXT DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_table_image_task_index (task_id, table_index),
  KEY idx_table_image_task_id (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS table_markdown (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  task_id VARCHAR(255) NOT NULL,
  table_image_id BIGINT UNSIGNED NOT NULL,
  markdown_content MEDIUMTEXT NOT NULL,
  markdown_path VARCHAR(1000) DEFAULT NULL,
  content_length INT NOT NULL DEFAULT 0,
  parser_type VARCHAR(50) NOT NULL DEFAULT 'mineru',
  parser_version VARCHAR(50) DEFAULT NULL,
  confidence_score DECIMAL(7,4) DEFAULT NULL,
  table_type VARCHAR(50) DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_table_markdown_image (table_image_id),
  KEY idx_table_markdown_task_id (task_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS standard_extracted (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  task_id VARCHAR(255) NOT NULL,
  table_markdown_id BIGINT UNSIGNED NOT NULL,
  original_text VARCHAR(255) NOT NULL,
  prefix VARCHAR(20) NOT NULL,
  standard_type VARCHAR(20) NOT NULL,
  number VARCHAR(80) NOT NULL,
  year VARCHAR(10) NOT NULL,
  has_t TINYINT(1) NOT NULL DEFAULT 0,
  row_index INT NOT NULL DEFAULT 0,
  col_index INT NOT NULL DEFAULT 0,
  cell_text TEXT DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_standard_extracted_position (task_id, original_text, row_index, col_index),
  KEY idx_standard_extracted_task_id (task_id),
  KEY idx_standard_extracted_markdown_id (table_markdown_id)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS standard_comparison (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  task_id VARCHAR(255) NOT NULL,
  standard_extracted_id BIGINT UNSIGNED NOT NULL,
  match_status VARCHAR(30) NOT NULL,
  match_score INT NOT NULL DEFAULT 0,
  matched_library_id BIGINT UNSIGNED DEFAULT NULL,
  matched_standard_no VARCHAR(255) DEFAULT NULL,
  matched_prefix VARCHAR(20) DEFAULT NULL,
  matched_number VARCHAR(80) DEFAULT NULL,
  matched_year VARCHAR(10) DEFAULT NULL,
  prefix_match TINYINT(1) NOT NULL DEFAULT 0,
  number_match TINYINT(1) NOT NULL DEFAULT 0,
  main_number_match TINYINT(1) NOT NULL DEFAULT 0,
  year_match TINYINT(1) NOT NULL DEFAULT 0,
  number_similarity DECIMAL(7,4) NOT NULL DEFAULT 0.0000,
  message VARCHAR(1000) DEFAULT NULL,
  created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  PRIMARY KEY (id),
  UNIQUE KEY uk_standard_comparison_extracted (standard_extracted_id),
  KEY idx_standard_comparison_task_id (task_id),
  KEY idx_standard_comparison_status (match_status)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;

CREATE TABLE IF NOT EXISTS standard_data (
  id BIGINT UNSIGNED NOT NULL AUTO_INCREMENT,
  standard_no VARCHAR(255) NOT NULL,
  standard_type VARCHAR(50) NOT NULL,
  standard_prefix VARCHAR(50) NOT NULL,
  create_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
  update_time DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
  create_user VARCHAR(100) NOT NULL DEFAULT 'ADMIN',
  update_user VARCHAR(100) NOT NULL DEFAULT 'ADMIN',
  PRIMARY KEY (id),
  UNIQUE KEY uk_standard_data_no (standard_no),
  KEY idx_standard_data_type (standard_type),
  KEY idx_standard_data_prefix (standard_prefix)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci;
