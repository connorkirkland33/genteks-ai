-- GenTeks AI Database Schema
-- Run this on the server: mysql -u root -p < schema.sql

CREATE DATABASE IF NOT EXISTS genteks_ai CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;

CREATE USER IF NOT EXISTS 'genteks'@'localhost' IDENTIFIED BY 'CHANGE_THIS_PASSWORD';
GRANT ALL PRIVILEGES ON genteks_ai.* TO 'genteks'@'localhost';
FLUSH PRIVILEGES;

USE genteks_ai;

-- Memories table
CREATE TABLE IF NOT EXISTS memories (
    id VARCHAR(64) PRIMARY KEY,
    content TEXT NOT NULL,
    agent_id VARCHAR(128) DEFAULT 'system',
    category VARCHAR(128) DEFAULT 'general',
    importance INT DEFAULT 5,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    metadata JSON,
    INDEX idx_agent (agent_id),
    INDEX idx_category (category),
    INDEX idx_timestamp (timestamp),
    FULLTEXT INDEX idx_content (content)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Chat sessions table (for Phase 3 persistent chat history)
CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(255) DEFAULT 'New Chat',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Chat messages table (for Phase 3 persistent chat history)
CREATE TABLE IF NOT EXISTS chat_messages (
    id BIGINT AUTO_INCREMENT PRIMARY KEY,
    session_id VARCHAR(64) NOT NULL,
    role ENUM('user','assistant','error') NOT NULL,
    content TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (session_id) REFERENCES chat_sessions(id) ON DELETE CASCADE,
    INDEX idx_session (session_id),
    INDEX idx_timestamp (timestamp)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;

-- Task log table (optional - for persistent task history)
CREATE TABLE IF NOT EXISTS task_logs (
    id VARCHAR(64) PRIMARY KEY,
    prompt TEXT NOT NULL,
    response TEXT,
    status ENUM('pending','running','complete','error') DEFAULT 'pending',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    completed_at DATETIME,
    duration_seconds INT,
    INDEX idx_status (status),
    INDEX idx_created (created_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
