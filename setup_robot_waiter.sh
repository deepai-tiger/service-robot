#!/bin/bash

# Step 1: Update and upgrade the system
echo "🔄 Updating system packages..."
sudo apt-get update && sudo apt-get upgrade -y

# Step 2: Install Chromium and Chromedriver
echo "🌐 Installing Chromium and Chromedriver..."
sudo apt-get install -y chromium-browser chromium-chromedriver

# Step 3: Set upstream branch and create virtual environment
echo "🐍 Setting Git upstream and Python environment..."
cd /home/pi/Documents/e20-3yp-The_Robot_Waiter || exit

git branch --set-upstream-to=origin/main main

python3 -m venv venv --system-site-packages
source venv/bin/activate

pip install -r requirements.txt

# Step 4: Create systemd service file for robotwaiter
echo "🛠️ Creating systemd service: robotwaiter.service..."
ROBOT_SERVICE_PATH="/etc/systemd/system/robotwaiter.service"

sudo tee $ROBOT_SERVICE_PATH > /dev/null <<EOF
[Unit]
Description=Start Robot Waiter Python Script on Boot
After=network.target

[Service]
ExecStart=/home/pi/Documents/e20-3yp-The_Robot_Waiter/start_robot.sh
WorkingDirectory=/home/pi/Documents/e20-3yp-The_Robot_Waiter
StandardOutput=inherit
StandardError=inherit
Restart=always
User=pi
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Step 5: Create systemd service for WiFi Manager Flask server
echo "🛠️ Creating systemd service: wifi_manager.service..."
WIFI_SERVICE_PATH="/etc/systemd/system/wifi_manager.service"

sudo tee $WIFI_SERVICE_PATH > /dev/null <<EOF
[Unit]
Description=WiFi Manager Web Interface
After=network.target

[Service]
User=pi
WorkingDirectory=/home/pi/Documents/e20-3yp-The_Robot_Waiter/code/main/
ExecStart=/home/pi/Documents/e20-3yp-The_Robot_Waiter/venv/bin/python3 wifi_manager.py
Restart=always
RestartSec=5
StandardOutput=journal
StandardError=journal
SyslogIdentifier=wifi_manager
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

# Step 6: Enable and start both services
echo "✅ Enabling and starting systemd services..."
sudo systemctl daemon-reexec
sudo systemctl daemon-reload

sudo systemctl enable robotwaiter.service
sudo systemctl enable wifi_manager.service

sudo systemctl start robotwaiter.service
sudo systemctl start wifi_manager.service

# Final message
echo "🎉 All setup complete!"
echo "👉 Check logs with:"
echo "   sudo journalctl -u robotwaiter.service -e"
echo "   sudo journalctl -u wifi_manager.service -e"
