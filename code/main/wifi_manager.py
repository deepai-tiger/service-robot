#!/usr/bin/env python3
import json
import os
import subprocess
import threading
import time
import re
from flask import Flask, render_template_string, request, jsonify
from pathlib import Path

# Constants
WIFI_CONFIG_FILE = Path("wifi_config.json")
ROBOT_CONFIG_FILE = Path("robot_config.json")
WPA_SUPPLICANT_CONF = "/etc/wpa_supplicant/wpa_supplicant.conf"

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>Raspberry Pi WiFi & Robot Setup</title>
    <meta name="viewport" content="width=device-width, initial-scale=1">
    <style>
        body { 
            font-family: Arial, sans-serif; 
            max-width: 800px; 
            margin: 0 auto; 
            padding: 20px; 
            background-color: #f5f5f5;
        }
        .container {
            background: white;
            padding: 20px;
            border-radius: 8px;
            box-shadow: 0 2px 10px rgba(0,0,0,0.1);
            margin-bottom: 20px;
        }
        .section-title {
            color: #333;
            border-bottom: 2px solid #007acc;
            padding-bottom: 10px;
            margin-bottom: 20px;
        }
        .network { 
            padding: 15px; 
            margin: 8px 0; 
            border: 1px solid #ddd; 
            cursor: pointer; 
            border-radius: 4px;
            background: #fafafa;
            display: flex;
            justify-content: space-between;
            align-items: center;
        }
        .network:hover { 
            background-color: #e8f4f8; 
            border-color: #007acc;
        }
        .network-info {
            display: flex;
            flex-direction: column;
        }
        .network-name {
            font-weight: bold;
            font-size: 16px;
        }
        .network-details {
            font-size: 12px;
            color: #666;
            margin-top: 2px;
        }
        .signal-strength {
            font-size: 12px;
            color: #007acc;
            font-weight: bold;
        }
        #passwordForm { 
            display: none; 
            background: #f0f8ff;
            padding: 20px;
            border-radius: 6px;
            margin-top: 20px;
        }
        .config-form {
            background: #f9f9f9;
            padding: 20px;
            border-radius: 6px;
            margin-top: 20px;
        }
        .form-group {
            margin-bottom: 15px;
        }
        .form-group label {
            display: block;
            margin-bottom: 5px;
            font-weight: bold;
            color: #333;
        }
        input[type="password"], input[type="text"] {
            width: 100%;
            padding: 10px;
            margin: 5px 0;
            border: 1px solid #ddd;
            border-radius: 4px;
            box-sizing: border-box;
        }
        button {
            background: #007acc;
            color: white;
            padding: 10px 20px;
            border: none;
            border-radius: 4px;
            cursor: pointer;
            margin-right: 10px;
        }
        button:hover {
            background: #005a99;
        }
        .cancel-btn {
            background: #666;
        }
        .cancel-btn:hover {
            background: #444;
        }
        .save-btn {
            background: #28a745;
        }
        .save-btn:hover {
            background: #218838;
        }
        .status {
            margin-top: 15px;
            padding: 10px;
            border-radius: 4px;
            display: none;
        }
        .status.success {
            background: #d4edda;
            color: #155724;
            border: 1px solid #c3e6cb;
        }
        .status.error {
            background: #f8d7da;
            color: #721c24;
            border: 1px solid #f5c6cb;
        }
        .status.info {
            background: #d1ecf1;
            color: #0c5460;
            border: 1px solid #bee5eb;
        }
        .loading {
            display: none;
            text-align: center;
            margin: 20px 0;
        }
        .refresh-btn {
            background: #28a745;
            margin-bottom: 20px;
        }
        .refresh-btn:hover {
            background: #218838;
        }
        .config-info {
            background: #e9ecef;
            padding: 10px;
            border-radius: 4px;
            margin-bottom: 15px;
            font-size: 12px;
            color: #495057;
        }
        .tab-container {
            margin-bottom: 20px;
        }
        .tab-buttons {
            display: flex;
            background: #e9ecef;
            border-radius: 8px 8px 0 0;
            overflow: hidden;
        }
        .tab-button {
            flex: 1;
            padding: 15px;
            background: #e9ecef;
            border: none;
            cursor: pointer;
            font-size: 16px;
            font-weight: bold;
            transition: background-color 0.3s;
        }
        .tab-button.active {
            background: #007acc;
            color: white;
        }
        .tab-button:hover:not(.active) {
            background: #dee2e6;
        }
        .tab-content {
            display: none;
        }
        .tab-content.active {
            display: block;
        }
    </style>
</head>
<body>
    <div class="tab-container">
        <div class="tab-buttons">
            <button class="tab-button active" onclick="switchTab('wifi')">📶 WiFi Setup</button>
            <button class="tab-button" onclick="switchTab('robot')">🤖 Robot Config</button>
        </div>
    </div>

    <!-- WiFi Tab -->
    <div id="wifi-tab" class="tab-content active">
        <div class="container">
            <h1 class="section-title">WiFi Network Setup</h1>
            <button class="refresh-btn" onclick="refreshNetworks()">🔄 Refresh Networks</button>
            <div class="loading" id="loading">Scanning for networks...</div>
            <div id="networks"></div>
            <div id="passwordForm">
                <h3>Connect to: <span id="selectedNetwork"></span></h3>
                <input type="password" id="password" placeholder="Enter WiFi password">
                <br>
                <button onclick="connectWifi()">Connect</button>
                <button class="cancel-btn" onclick="hidePasswordForm()">Cancel</button>
            </div>
            <div id="wifi-status" class="status"></div>
        </div>
    </div>

    <!-- Robot Config Tab -->
    <div id="robot-tab" class="tab-content">
        <div class="container">
            <h1 class="section-title">Robot Configuration</h1>
            <div class="config-info">
                Configure your robot's ID and password. These settings are saved to robot_config.json.
            </div>
            <div class="config-form">
                <div class="form-group">
                    <label for="robotId">Robot ID:</label>
                    <input type="text" id="robotId" placeholder="Enter Robot ID (e.g., ROBOwfyN)">
                </div>
                <div class="form-group">
                    <label for="robotPassword">Robot Password:</label>
                    <input type="text" id="robotPassword" placeholder="Enter Robot Password">
                </div>
                <button class="save-btn" onclick="saveRobotConfig()">💾 Save Configuration</button>
                <button onclick="loadRobotConfig()">🔄 Reload</button>
            </div>
            <div id="robot-status" class="status"></div>
        </div>
    </div>

    <script>
        let selectedSSID = '';
        
        // Tab switching
        function switchTab(tabName) {
            // Hide all tabs
            document.querySelectorAll('.tab-content').forEach(tab => {
                tab.classList.remove('active');
            });
            document.querySelectorAll('.tab-button').forEach(btn => {
                btn.classList.remove('active');
            });
            
            // Show selected tab
            document.getElementById(tabName + '-tab').classList.add('active');
            document.querySelector(`[onclick="switchTab('${tabName}')"]`).classList.add('active');
            
            // Load data for the active tab
            if (tabName === 'wifi') {
                loadNetworks();
            } else if (tabName === 'robot') {
                loadRobotConfig();
            }
        }
        
        // WiFi Functions
        function loadNetworks() {
            document.getElementById('loading').style.display = 'block';
            document.getElementById('networks').innerHTML = '';
            
            fetch('/scan')
                .then(response => response.json())
                .then(data => {
                    document.getElementById('loading').style.display = 'none';
                    if (data.success) {
                        displayNetworks(data.networks);
                    } else {
                        showWifiStatus('Failed to scan networks: ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    document.getElementById('loading').style.display = 'none';
                    showWifiStatus('Error scanning networks: ' + error.message, 'error');
                });
        }

        function displayNetworks(networks) {
            const networksDiv = document.getElementById('networks');
            networksDiv.innerHTML = '';
            
            if (networks.length === 0) {
                networksDiv.innerHTML = '<p>No networks found. Try refreshing.</p>';
                return;
            }
            
            networks.forEach(network => {
                const div = document.createElement('div');
                div.className = 'network';
                div.innerHTML = `
                    <div class="network-info">
                        <div class="network-name">${network.ssid}</div>
                        <div class="network-details">${network.encryption} • Channel ${network.channel}</div>
                    </div>
                    <div class="signal-strength">${network.signal_strength}%</div>
                `;
                div.onclick = () => showPasswordForm(network.ssid, network.encryption);
                networksDiv.appendChild(div);
            });
        }

        function showPasswordForm(ssid, encryption) {
            selectedSSID = ssid;
            document.getElementById('passwordForm').style.display = 'block';
            document.getElementById('selectedNetwork').textContent = ssid;
            document.getElementById('password').focus();
            hideWifiStatus();
        }

        function hidePasswordForm() {
            document.getElementById('passwordForm').style.display = 'none';
            document.getElementById('password').value = '';
            selectedSSID = '';
        }

        function connectWifi() {
            const password = document.getElementById('password').value;
            
            if (!selectedSSID) {
                showWifiStatus('No network selected', 'error');
                return;
            }
            
            showWifiStatus('Connecting to ' + selectedSSID + '...', 'info');
            
            fetch('/connect', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({ssid: selectedSSID, password: password})
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showWifiStatus(data.message, 'success');
                    hidePasswordForm();
                } else {
                    showWifiStatus(data.message, 'error');
                }
            })
            .catch(error => {
                showWifiStatus('Connection error: ' + error.message, 'error');
            });
        }

        function refreshNetworks() {
            loadNetworks();
        }

        function showWifiStatus(message, type) {
            const statusDiv = document.getElementById('wifi-status');
            statusDiv.textContent = message;
            statusDiv.className = 'status ' + type;
            statusDiv.style.display = 'block';
            
            if (type === 'success') {
                setTimeout(hideWifiStatus, 5000);
            }
        }

        function hideWifiStatus() {
            document.getElementById('wifi-status').style.display = 'none';
        }

        // Robot Config Functions
        function loadRobotConfig() {
            fetch('/robot-config')
                .then(response => response.json())
                .then(data => {
                    if (data.success) {
                        document.getElementById('robotId').value = data.config.robotId || '';
                        document.getElementById('robotPassword').value = data.config.password || '';
                        showRobotStatus('Configuration loaded successfully', 'success');
                    } else {
                        showRobotStatus('Failed to load configuration: ' + data.message, 'error');
                    }
                })
                .catch(error => {
                    showRobotStatus('Error loading configuration: ' + error.message, 'error');
                });
        }

        function saveRobotConfig() {
            const robotId = document.getElementById('robotId').value.trim();
            const robotPassword = document.getElementById('robotPassword').value.trim();
            
            if (!robotId) {
                showRobotStatus('Robot ID is required', 'error');
                return;
            }
            
            if (!robotPassword) {
                showRobotStatus('Robot Password is required', 'error');
                return;
            }
            
            showRobotStatus('Saving configuration...', 'info');
            
            fetch('/robot-config', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify({
                    robotId: robotId,
                    password: robotPassword
                })
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    showRobotStatus(data.message, 'success');
                } else {
                    showRobotStatus(data.message, 'error');
                }
            })
            .catch(error => {
                showRobotStatus('Save error: ' + error.message, 'error');
            });
        }

        function showRobotStatus(message, type) {
            const statusDiv = document.getElementById('robot-status');
            statusDiv.textContent = message;
            statusDiv.className = 'status ' + type;
            statusDiv.style.display = 'block';
            
            if (type === 'success') {
                setTimeout(hideRobotStatus, 3000);
            }
        }

        function hideRobotStatus() {
            document.getElementById('robot-status').style.display = 'none';
        }

        // Initialize
        document.addEventListener('DOMContentLoaded', function() {
            // Load initial data
            loadNetworks();
            
            // Enter key support for password field
            document.getElementById('password').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    connectWifi();
                }
            });
            
            // Enter key support for robot config fields
            document.getElementById('robotId').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    saveRobotConfig();
                }
            });
            
            document.getElementById('robotPassword').addEventListener('keypress', function(e) {
                if (e.key === 'Enter') {
                    saveRobotConfig();
                }
            });
        });
    </script>
</body>
</html>
"""

app = Flask(__name__)

def run_command(command, timeout=30):
    """Run a system command with timeout"""
    try:
        result = subprocess.run(
            command, 
            shell=True, 
            capture_output=True, 
            text=True, 
            timeout=timeout
        )
        return result.returncode == 0, result.stdout, result.stderr
    except subprocess.TimeoutExpired:
        return False, "", "Command timed out"
    except Exception as e:
        return False, "", str(e)

def get_wifi_interface():
    """Get the WiFi interface name"""
    success, output, _ = run_command("ls /sys/class/net/ | grep -E '^wl'")
    if success and output.strip():
        return output.strip().split('\n')[0]
    return "wlan0"  # Default fallback

def scan_wifi_networks():
    """Scan for available WiFi networks using nmcli or iwlist"""
    interface = get_wifi_interface()
    networks = []
    
    # Try nmcli first (NetworkManager)
    success, output, _ = run_command("which nmcli")
    if success:
        success, output, error = run_command("nmcli -t -f SSID,SIGNAL,SECURITY,CHAN dev wifi list")
        if success:
            for line in output.strip().split('\n'):
                if line and ':' in line:
                    parts = line.split(':')
                    if len(parts) >= 4 and parts[0].strip():
                        ssid = parts[0].strip()
                        signal = parts[1].strip() if parts[1] else "0"
                        security = parts[2].strip() if parts[2] else "Open"
                        channel = parts[3].strip() if parts[3] else "Unknown"
                        
                        # Skip hidden networks
                        if ssid and ssid != "--":
                            networks.append({
                                'ssid': ssid,
                                'signal_strength': signal,
                                'encryption': security if security else "Open",
                                'channel': channel
                            })
    
    # Fallback to iwlist if nmcli failed
    if not networks:
        success, output, _ = run_command(f"sudo iwlist {interface} scan")
        if success:
            networks = parse_iwlist_output(output)
    
    # Remove duplicates and sort by signal strength
    seen_ssids = set()
    unique_networks = []
    for network in networks:
        if network['ssid'] not in seen_ssids:
            seen_ssids.add(network['ssid'])
            unique_networks.append(network)
    
    # Sort by signal strength (descending)
    try:
        unique_networks.sort(key=lambda x: int(str(x['signal_strength']).replace('%', '').replace('dBm', '')), reverse=True)
    except:
        pass
    
    return unique_networks

def parse_iwlist_output(output):
    """Parse iwlist scan output"""
    networks = []
    current_network = {}
    
    for line in output.split('\n'):
        line = line.strip()
        
        if 'Cell' in line and 'Address:' in line:
            if current_network.get('ssid'):
                networks.append(current_network)
            current_network = {}
        
        elif 'ESSID:' in line:
            ssid_match = re.search(r'ESSID:"([^"]*)"', line)
            if ssid_match:
                current_network['ssid'] = ssid_match.group(1)
        
        elif 'Signal level=' in line:
            signal_match = re.search(r'Signal level=(-?\d+)', line)
            if signal_match:
                # Convert dBm to percentage (rough approximation)
                dbm = int(signal_match.group(1))
                percentage = max(0, min(100, 2 * (dbm + 100)))
                current_network['signal_strength'] = str(percentage)
        
        elif 'Encryption key:' in line:
            if 'off' in line:
                current_network['encryption'] = 'Open'
            else:
                current_network['encryption'] = 'WPA/WPA2'
        
        elif 'Channel:' in line:
            channel_match = re.search(r'Channel:(\d+)', line)
            if channel_match:
                current_network['channel'] = channel_match.group(1)
    
    # Add the last network
    if current_network.get('ssid'):
        networks.append(current_network)
    
    return networks

def connect_to_wifi_nmcli(ssid, password):
    """Connect using NetworkManager (nmcli)"""
    # Check if NetworkManager is available
    success, _, _ = run_command("which nmcli")
    if not success:
        return False, "NetworkManager not available"
    
    # Remove existing connection if it exists
    run_command(f'nmcli connection delete "{ssid}"')
    
    # Create new connection
    if password:
        success, output, error = run_command(
            f'nmcli device wifi connect "{ssid}" password "{password}"'
        )
    else:
        success, output, error = run_command(
            f'nmcli device wifi connect "{ssid}"'
        )
    
    if success:
        return True, f"Successfully connected to {ssid}"
    else:
        return False, f"Failed to connect: {error}"

def connect_to_wifi_wpa(ssid, password):
    """Connect using wpa_supplicant (fallback method)"""
    interface = get_wifi_interface()
    
    try:
        # Create wpa_supplicant config
        config_content = f"""country=US
ctrl_interface=DIR=/var/run/wpa_supplicant GROUP=netdev
update_config=1

network={{
    ssid="{ssid}"
    """
        
        if password:
            config_content += f'    psk="{password}"\n'
        else:
            config_content += '    key_mgmt=NONE\n'
        
        config_content += "}\n"
        
        # Write config file
        with open('/tmp/wpa_temp.conf', 'w') as f:
            f.write(config_content)
        
        # Copy to system location
        success, _, error = run_command('sudo cp /tmp/wpa_temp.conf /etc/wpa_supplicant/wpa_supplicant.conf')
        if not success:
            return False, f"Failed to write config: {error}"
        
        # Restart network interface
        run_command(f'sudo ifconfig {interface} down')
        time.sleep(2)
        run_command(f'sudo ifconfig {interface} up')
        
        # Restart wpa_supplicant
        run_command('sudo systemctl restart wpa_supplicant')
        time.sleep(3)
        
        # Request DHCP
        run_command(f'sudo dhclient {interface}')
        
        # Check connection
        for i in range(15):
            success, output, _ = run_command('iwgetid -r')
            if success and ssid in output:
                return True, f"Successfully connected to {ssid}"
            time.sleep(2)
        
        return False, "Connection timeout"
        
    except Exception as e:
        return False, f"Connection failed: {str(e)}"

def save_wifi_config(ssid, password):
    """Save WiFi credentials to local file"""
    config = {'ssid': ssid, 'password': password, 'timestamp': time.time()}
    try:
        with open(WIFI_CONFIG_FILE, 'w') as f:
            json.dump(config, f)
        return True
    except Exception as e:
        print(f"Failed to save config: {e}")
        return False

def load_wifi_config():
    """Load saved WiFi credentials"""
    try:
        if WIFI_CONFIG_FILE.exists():
            with open(WIFI_CONFIG_FILE, 'r') as f:
                return json.load(f)
    except Exception as e:
        print(f"Failed to load config: {e}")
    return None

def load_robot_config():
    """Load robot configuration from JSON file"""
    try:
        if ROBOT_CONFIG_FILE.exists():
            with open(ROBOT_CONFIG_FILE, 'r') as f:
                return json.load(f)
        else:
            # Return default structure if file doesn't exist
            return {
                "robotId": "",
                "password": "",
                "lastUpdated": time.time()
            }
    except Exception as e:
        print(f"Failed to load robot config: {e}")
        return None

def save_robot_config(robot_id, password):
    """Save robot configuration to JSON file"""
    config = {
        "robotId": robot_id,
        "password": password,
        "lastUpdated": time.time()
    }
    try:
        with open(ROBOT_CONFIG_FILE, 'w') as f:
            json.dump(config, f, indent=2)
        return True, "Robot configuration saved successfully"
    except Exception as e:
        print(f"Failed to save robot config: {e}")
        return False, f"Failed to save configuration: {str(e)}"

def check_internet_connectivity():
    """Check if we have internet connectivity"""
    success, _, _ = run_command("ping -c 1 -W 5 8.8.8.8")
    return success

@app.route('/')
def home():
    return render_template_string(HTML_TEMPLATE)

@app.route('/scan')
def scan():
    try:
        networks = scan_wifi_networks()
        return jsonify({
            'success': True,
            'networks': networks
        })
    except Exception as e:
        return jsonify({
            'success': False,
            'message': str(e),
            'networks': []
        })

@app.route('/connect', methods=['POST'])
def connect():
    try:
        data = request.json
        ssid = data.get('ssid', '').strip()
        password = data.get('password', '').strip()
        
        if not ssid:
            return jsonify({
                'success': False,
                'message': 'SSID is required'
            })
        
        # Try NetworkManager first
        success, message = connect_to_wifi_nmcli(ssid, password)
        
        # Fallback to wpa_supplicant if NetworkManager fails
        if not success:
            success, message = connect_to_wifi_wpa(ssid, password)
        
        if success:
            save_wifi_config(ssid, password)

            # Disable AP mode (stop hostapd and dnsmasq)
            run_command("sudo systemctl stop hostapd")
            run_command("sudo systemctl stop dnsmasq")
            run_command("sudo systemctl disable hostapd")
            run_command("sudo systemctl disable dnsmasq")

            # Wait and try to get IP address
            time.sleep(3)
            run_command("sudo dhclient wlan0")

            time.sleep(5)
            if check_internet_connectivity():
                message += " - Internet connectivity confirmed"
            else:
                message += " - Connected but no internet access"
        
        return jsonify({
            'success': success,
            'message': message
        })
        
    except Exception as e:
        return jsonify({
            'success': False,
            'message': f'Connection error: {str(e)}'
        })

@app.route('/robot-config', methods=['GET', 'POST'])
def robot_config():
    if request.method == 'GET':
        try:
            config = load_robot_config()
            if config is not None:
                return jsonify({
                    'success': True,
                    'config': config
                })
            else:
                return jsonify({
                    'success': False,
                    'message': 'Failed to load robot configuration'
                })
        except Exception as e:
            return jsonify({
                'success': False,
                'message': str(e)
            })
    
    elif request.method == 'POST':
        try:
            data = request.json
            robot_id = data.get('robotId', '').strip()
            password = data.get('password', '').strip()
            
            if not robot_id:
                return jsonify({
                    'success': False,
                    'message': 'Robot ID is required'
                })
            
            if not password:
                return jsonify({
                    'success': False,
                    'message': 'Robot password is required'
                })
            
            success, message = save_robot_config(robot_id, password)
            
            return jsonify({
                'success': success,
                'message': message
            })
            
        except Exception as e:
            return jsonify({
                'success': False,
                'message': f'Save error: {str(e)}'
            })

@app.route('/status')
def status():
    """Get current WiFi status"""
    try:
        success, output, _ = run_command('iwgetid -r')
        current_ssid = output.strip() if success else None
        
        internet = check_internet_connectivity()
        
        return jsonify({
            'connected': bool(current_ssid),
            'ssid': current_ssid,
            'internet': internet
        })
    except Exception as e:
        return jsonify({
            'connected': False,
            'ssid': None,
            'internet': False,
            'error': str(e)
        })

def start_web_server():
    """Start the Flask web server"""
    app.run(host='0.0.0.0', port=8000, debug=False)

def main():
    """Main function"""
    print("=== Raspberry Pi WiFi & Robot Setup Tool ===")
    
    # Check if running as root/sudo for system operations
    if os.geteuid() != 0:
        print("Warning: Not running as root. Some operations may fail.")
        print("Consider running with: sudo python3 wifi_setup.py")
    
    # Try to connect with saved credentials first
    config = load_wifi_config()
    if config and config.get('ssid'):
        print(f"Attempting to connect to saved network: {config['ssid']}")
        success, message = connect_to_wifi_nmcli(config['ssid'], config.get('password', ''))
        if success:
            print("✓ Connected to saved network successfully")
        else:
            print(f"✗ Failed to connect to saved network: {message}")
    
    # Check robot config
    robot_config = load_robot_config()
    if robot_config and robot_config.get('robotId'):
        print(f"✓ Robot config loaded - ID: {robot_config['robotId']}")
    else:
        print("⚠ Robot configuration not found or incomplete")
    
    # Start web server
    server_thread = threading.Thread(target=start_web_server)
    server_thread.daemon = True
    server_thread.start()

    # Start WiFi monitor thread
    monitor_thread = threading.Thread(target=monitor_wifi_connection)
    monitor_thread.daemon = True
    monitor_thread.start()

    
    print(f"\n🌐 Web interface started!")
    print(f"   Local access: http://localhost:8000")
    
    # Try to get IP address for remote access
    success, output, _ = run_command("hostname -I")
    if success and output.strip():
        ip = output.strip().split()[0]
        print(f"   Network access: http://{ip}:8000")
    
    print(f"\n📱 Features available:")
    print(f"   • WiFi network scanning and connection")
    print(f"   • Robot configuration management")
    print(f"   • Configuration file editing via web interface")
    print(f"   Press Ctrl+C to stop the server")
    
    try:
        while True:
            time.sleep(1)
    except KeyboardInterrupt:
        print("\n\n🛑 Shutting down setup tool...")

def monitor_wifi_connection(interval=20, fail_threshold=3):
    """Monitor WiFi and fallback to hotspot if lost"""
    print("[Monitor] WiFi monitor thread started")
    fails = 0

    while True:
        # Check if connected to a WiFi network
        success, ssid, _ = run_command('iwgetid -r')

        if success and ssid.strip():
            print(f"[Monitor] Connected to SSID: {ssid.strip()}")
            fails = 0
        else:
            fails += 1
            print(f"[Monitor] WiFi check failed ({fails}/{fail_threshold})")

        # After too many failures, try enabling hotspot
        if fails >= fail_threshold:
            print("[Monitor] Re-enabling hotspot due to connection loss")

            # Stop wpa_supplicant to release wlan0
            run_command("sudo systemctl stop wpa_supplicant")
            run_command("sudo systemctl disable wpa_supplicant")

            # Start hostapd and dnsmasq
            run_command("sudo systemctl unmask hostapd")
            run_command("sudo systemctl enable hostapd")
            run_command("sudo systemctl enable dnsmasq")
            run_command("sudo systemctl restart hostapd")
            run_command("sudo systemctl restart dnsmasq")

            # Log status
            success, out, err = run_command("sudo systemctl status hostapd")
            print("[Monitor] hostapd status:\n", out, err)

            fails = 0  # Reset after fallback

        time.sleep(interval)

if __name__ == "__main__":
    main()