#!/bin/bash

echo "⏹️ Temporarily stopping robotwaiter.service..."

# Stop the service without disabling it
sudo systemctl stop robotwaiter.service

# Check status
sudo systemctl status robotwaiter.service --no-pager

echo "✅ robotwaiter.service stopped temporarily. It will start again on next reboot or if started manually."

