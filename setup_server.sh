#!/bin/bash
# GenTeks AI - Server Setup Script
# Run this on the Ubuntu 24.04 server after SSH access is established
# Usage: bash setup_server.sh

set -e
echo "======================================"
echo "  GenTeks AI Server Setup"
echo "======================================"

# ========================
# VARIABLES - UPDATE THESE
# ========================
GITHUB_REPO="https://github.com/connorkirkland33/genteks-ai.git"
APP_USER="genteks"
APP_DIR="/home/genteks/openmanus"
DB_NAME="genteks_ai"
DB_USER="genteks"
# DB_PASS will be prompted

# ========================
# SYSTEM UPDATES
# ========================
echo "[1/8] Updating system packages..."
sudo apt update && sudo apt upgrade -y

# ========================
# INSTALL DEPENDENCIES
# ========================
echo "[2/8] Installing Python, Git, and tools..."
sudo apt install -y python3.12 python3.12-venv python3-pip git curl ufw

# ========================
# INSTALL MYSQL
# ========================
echo "[3/8] Installing MySQL 8.0..."
sudo apt install -y mysql-server
sudo systemctl start mysql
sudo systemctl enable mysql

# ========================
# CREATE APP USER
# ========================
echo "[4/8] Creating app user..."
if ! id "$APP_USER" &>/dev/null; then
    sudo useradd -m -s /bin/bash $APP_USER
    echo "User '$APP_USER' created."
else
    echo "User '$APP_USER' already exists."
fi

# ========================
# CLONE REPO
# ========================
echo "[5/8] Cloning repository..."
sudo -u $APP_USER git clone $GITHUB_REPO $APP_DIR
echo "Repository cloned to $APP_DIR"

# ========================
# PYTHON VENV + DEPS
# ========================
echo "[6/8] Setting up Python virtual environment..."
sudo -u $APP_USER python3.12 -m venv $APP_DIR/.venv
sudo -u $APP_USER $APP_DIR/.venv/bin/pip install --upgrade pip
sudo -u $APP_USER $APP_DIR/.venv/bin/pip install -r $APP_DIR/ManusProjects/requirements.txt

# ========================
# SETUP DATABASE
# ========================
echo "[7/8] Setting up MySQL database..."
read -sp "Enter MySQL root password: " MYSQL_ROOT_PASS
echo
read -sp "Enter password for genteks DB user: " DB_PASS
echo

mysql -u root -p"$MYSQL_ROOT_PASS" << EOF
CREATE DATABASE IF NOT EXISTS $DB_NAME CHARACTER SET utf8mb4 COLLATE utf8mb4_unicode_ci;
CREATE USER IF NOT EXISTS '$DB_USER'@'localhost' IDENTIFIED BY '$DB_PASS';
GRANT ALL PRIVILEGES ON $DB_NAME.* TO '$DB_USER'@'localhost';
FLUSH PRIVILEGES;
USE $DB_NAME;
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
CREATE TABLE IF NOT EXISTS chat_sessions (
    id VARCHAR(64) PRIMARY KEY,
    title VARCHAR(255) DEFAULT 'New Chat',
    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
    INDEX idx_updated (updated_at)
) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4;
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
EOF

echo "Database and tables created successfully."

# ========================
# CONFIG FILE
# ========================
echo ""
echo "======================================"
echo "  IMPORTANT: Manual config step"
echo "======================================"
echo "You need to create the config file at:"
echo "  $APP_DIR/ManusProjects/config/config.toml"
echo ""
echo "Copy from the example and fill in your values:"
echo "  cp $APP_DIR/ManusProjects/config/config.example.toml $APP_DIR/ManusProjects/config/config.toml"
echo "  nano $APP_DIR/ManusProjects/config/config.toml"
echo ""
echo "Add these values:"
echo "  [llm] api_key = YOUR_ANTHROPIC_KEY"
echo "  [database] host=localhost user=genteks password=$DB_PASS database=genteks_ai"
echo ""
read -p "Press Enter once you have created and saved config.toml..."

# ========================
# SYSTEMD SERVICE
# ========================
echo "[8/8] Installing systemd service..."
sudo cp $APP_DIR/genteks-ai.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable genteks-ai
sudo systemctl start genteks-ai

# ========================
# FIREWALL
# ========================
echo "Configuring firewall..."
sudo ufw allow ssh
sudo ufw allow 8000
sudo ufw --force enable

# ========================
# DONE
# ========================
echo ""
echo "======================================"
echo "  Setup Complete!"
echo "======================================"
echo ""
echo "Service status:"
sudo systemctl status genteks-ai --no-pager
echo ""
SERVER_IP=$(hostname -I | awk '{print $1}')
echo "Access GenTeks AI at: http://$SERVER_IP:8000"
echo ""
echo "Useful commands:"
echo "  sudo systemctl status genteks-ai   # check status"
echo "  sudo systemctl restart genteks-ai  # restart"
echo "  sudo journalctl -u genteks-ai -f   # view logs"
echo ""
