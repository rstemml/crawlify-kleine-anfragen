#!/bin/bash
#
# Install systemd timer for crawlify-kleine-anfragen
#
# Usage:
#   sudo ./scripts/install-systemd.sh
#
# This script:
# 1. Copies service and timer files to /etc/systemd/system/
# 2. Reloads systemd daemon
# 3. Enables and starts the timer
#

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_DIR="$(dirname "$SCRIPT_DIR")"
SYSTEMD_DIR="/etc/systemd/system"

# Check if running as root
if [[ $EUID -ne 0 ]]; then
    echo "Error: This script must be run as root (use sudo)"
    exit 1
fi

echo "Installing crawlify systemd timer..."

# Copy service and timer files
echo "  Copying service file..."
cp "$PROJECT_DIR/systemd/crawlify-update.service" "$SYSTEMD_DIR/"

echo "  Copying timer file..."
cp "$PROJECT_DIR/systemd/crawlify-update.timer" "$SYSTEMD_DIR/"

# Reload systemd
echo "  Reloading systemd daemon..."
systemctl daemon-reload

# Enable and start timer
echo "  Enabling timer..."
systemctl enable crawlify-update.timer

echo "  Starting timer..."
systemctl start crawlify-update.timer

# Show status
echo ""
echo "Installation complete!"
echo ""
echo "Timer status:"
systemctl status crawlify-update.timer --no-pager

echo ""
echo "Next scheduled run:"
systemctl list-timers crawlify-update.timer --no-pager

echo ""
echo "Useful commands:"
echo "  - Check timer status:  systemctl status crawlify-update.timer"
echo "  - Check service logs:  journalctl -u crawlify-update.service"
echo "  - Run manually:        sudo systemctl start crawlify-update.service"
echo "  - Disable timer:       sudo systemctl disable crawlify-update.timer"
