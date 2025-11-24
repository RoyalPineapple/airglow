#!/usr/bin/env bash
# LedFx AirPlay Docker Stack Installer
# Installs Docker (if needed) and starts the LedFx + Shairport-Sync stack

set -Eeuo pipefail

INSTALL_DIR="/opt/ledfx-airplay"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

function msg_info() {
    echo -e "\033[0;34mℹ\033[0m $1"
}

function msg_ok() {
    echo -e "\033[0;32m✓\033[0m $1"
}

function msg_error() {
    echo -e "\033[0;31m✗\033[0m $1" >&2
}

function check_root() {
    if [[ "$(id -u)" -ne 0 ]]; then
        msg_error "This script must be run as root (use sudo)"
        exit 1
    fi
}

function install_docker() {
    if command -v docker &>/dev/null; then
        msg_ok "Docker already installed"
        return 0
    fi
    
    msg_info "Installing Docker..."
    
    # Update package index
    apt-get update -qq
    
    # Install prerequisites
    apt-get install -y -qq \
        ca-certificates \
        curl \
        gnupg \
        lsb-release
    
    # Add Docker's official GPG key
    install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://download.docker.com/linux/debian/gpg | gpg --dearmor -o /etc/apt/keyrings/docker.gpg
    chmod a+r /etc/apt/keyrings/docker.gpg
    
    # Set up repository
    echo \
      "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/docker.gpg] https://download.docker.com/linux/debian \
      $(lsb_release -cs) stable" | tee /etc/apt/sources.list.d/docker.list > /dev/null
    
    # Install Docker
    apt-get update -qq
    apt-get install -y -qq docker-ce docker-ce-cli containerd.io docker-compose-plugin
    
    # Start and enable Docker
    systemctl start docker
    systemctl enable docker
    
    msg_ok "Docker installed successfully"
}

function setup_directory() {
    msg_info "Setting up installation directory..."
    
    if [[ -d "${INSTALL_DIR}" ]]; then
        msg_info "Installation directory exists, backing up..."
        mv "${INSTALL_DIR}" "${INSTALL_DIR}.backup.$(date +%s)"
    fi
    
    mkdir -p "${INSTALL_DIR}"
    mkdir -p "${INSTALL_DIR}/configs"
    mkdir -p "${INSTALL_DIR}/pulse"
    
    # Set ownership for Pulse directory (LedFx runs as UID 1000)
    chown -R 1000:1000 "${INSTALL_DIR}/pulse"
    
    msg_ok "Directory structure created"
}

function copy_configs() {
    msg_info "Copying configuration files..."
    
    cp "${SCRIPT_DIR}/docker-compose.yml" "${INSTALL_DIR}/"
    cp -r "${SCRIPT_DIR}/configs"/* "${INSTALL_DIR}/configs/"
    
    msg_ok "Configuration files copied"
}

function start_stack() {
    msg_info "Starting LedFx AirPlay stack..."
    
    cd "${INSTALL_DIR}"
    docker compose up -d
    
    msg_ok "Stack started successfully"
}

function show_status() {
    echo ""
    echo "=========================================="
    echo "LedFx AirPlay Installation Complete!"
    echo "=========================================="
    echo ""
    echo "Services:"
    docker compose -f "${INSTALL_DIR}/docker-compose.yml" ps
    echo ""
    echo "Access LedFx web UI: http://localhost:8888"
    echo ""
    echo "AirPlay device name: LEDFx AirPlay"
    echo "(Should appear in your device's AirPlay menu)"
    echo ""
    echo "Useful commands:"
    echo "  View logs:    docker compose -f ${INSTALL_DIR}/docker-compose.yml logs -f"
    echo "  Restart:      docker compose -f ${INSTALL_DIR}/docker-compose.yml restart"
    echo "  Stop:         docker compose -f ${INSTALL_DIR}/docker-compose.yml down"
    echo "  Update:       docker compose -f ${INSTALL_DIR}/docker-compose.yml pull && docker compose -f ${INSTALL_DIR}/docker-compose.yml up -d"
    echo ""
}

# Main installation flow
check_root
install_docker
setup_directory
copy_configs
start_stack
show_status

