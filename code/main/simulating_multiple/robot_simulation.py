import json
import tkinter as tk
from tkinter import ttk, messagebox, filedialog, simpledialog
import threading
import time
import math
import os
from dataclasses import dataclass, field
from typing import Dict, List, Optional
from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
import random

# --- Certificate Paths (relative to the script) ---
# Ensure these files are in your 'cert' folder.
ROOT_CA_PATH = os.path.join(os.path.dirname(__file__), "cert", "AmazonRootCA1.pem")
PRIVATE_KEY_PATH = os.path.join(os.path.dirname(__file__), "cert", "private.pem.key")
CERTIFICATE_PATH = os.path.join(os.path.dirname(__file__), "cert", "device-certificate.pem.crt")

# --- AWS IoT Endpoint (replace with your actual endpoint) ---
# You need to fill this in!
AWS_IOT_ENDPOINT = "a2cdp9hijgdiig-ats.iot.ap-southeast-2.amazonaws.com" # e.g., "xxxxxxxxxxxxxx-ats.iot.us-east-1.amazonaws.com"
AWS_REGION = "ap-southeast-2" # e.g., "us-east-1" (optional for certificate auth, but good to keep consistent)

@dataclass
class Robot:
    """Represents a robot in the simulation"""
    id: str
    x: float = 400  # Canvas position
    y: float = 300
    angle: float = 0  # Rotation angle in degrees
    color: str = "blue"
    mqtt_client: Optional[AWSIoTMQTTClient] = None
    topic: str = ""
    status: str = "disconnected"
    battery_level: float = 100.0
    last_command: str = ""
    last_command_time: float = 0
    # Movement state
    is_moving: bool = False
    target_angle: float = 0
    movement_start_time: float = 0
    movement_duration: float = 0
    movement_type: str = ""  # "forward", "backward", "left", "right"
    
    # Store endpoint for consistency, although certificates are primary auth
    aws_endpoint: str = ""
    
    def __post_init__(self):
        if not self.color or self.color == "blue":
            # Generate random color for each robot
            colors = ["red", "green", "blue", "purple", "orange", "brown", "pink", "cyan"]
            self.color = random.choice(colors)

class RobotSimulation:
    def __init__(self):
        self.root = tk.Tk()
        self.root.title("Multi-Robot MQTT Control Simulation")
        self.root.geometry("1200x800")
        
        self.robots: Dict[str, Robot] = {}
        self.canvas = None
        self.running = False
        self.animation_thread = None
        
        self.setup_gui()
        
    def setup_gui(self):
        """Setup the GUI components"""
        # Main frame
        main_frame = ttk.Frame(self.root)
        main_frame.pack(fill=tk.BOTH, expand=True, padx=10, pady=10)
        
        # Left panel for controls
        left_panel = ttk.Frame(main_frame, width=300)
        left_panel.pack(side=tk.LEFT, fill=tk.Y, padx=(0, 10))
        left_panel.pack_propagate(False)
        
        # Robot management
        robot_frame = ttk.LabelFrame(left_panel, text="Robot Management", padding=10)
        robot_frame.pack(fill=tk.X, pady=(0, 10))
        
        ttk.Button(robot_frame, text="Load Robot Config", 
                  command=self.load_robot_config).pack(fill=tk.X, pady=2)
        
        ttk.Button(robot_frame, text="Add Manual Robot", 
                  command=self.add_manual_robot).pack(fill=tk.X, pady=2)
        
        ttk.Button(robot_frame, text="Connect All Robots", 
                  command=self.connect_all_robots).pack(fill=tk.X, pady=2)
        
        ttk.Button(robot_frame, text="Disconnect All", 
                  command=self.disconnect_all_robots).pack(fill=tk.X, pady=2)
        
        # Robot list
        list_frame = ttk.LabelFrame(left_panel, text="Connected Robots", padding=10)
        list_frame.pack(fill=tk.BOTH, expand=True, pady=(0, 10))
        
        # Create treeview for robot list
        self.robot_tree = ttk.Treeview(list_frame, columns=("Status", "Battery", "Last Command"), 
                                      show="tree headings", height=10)
        self.robot_tree.heading("#0", text="Robot ID")
        self.robot_tree.heading("Status", text="Status")
        self.robot_tree.heading("Battery", text="Battery")
        self.robot_tree.heading("Last Command", text="Last Command")
        
        self.robot_tree.column("#0", width=100)
        self.robot_tree.column("Status", width=80)
        self.robot_tree.column("Battery", width=60)
        self.robot_tree.column("Last Command", width=80)
        
        scrollbar = ttk.Scrollbar(list_frame, orient=tk.VERTICAL, command=self.robot_tree.yview)
        self.robot_tree.configure(yscrollcommand=scrollbar.set)
        
        self.robot_tree.pack(side=tk.LEFT, fill=tk.BOTH, expand=True)
        scrollbar.pack(side=tk.RIGHT, fill=tk.Y)
        
        # Control buttons
        control_frame = ttk.LabelFrame(left_panel, text="Simulation Control", padding=10)
        control_frame.pack(fill=tk.X)
        
        ttk.Button(control_frame, text="Start Simulation", 
                  command=self.start_simulation).pack(fill=tk.X, pady=2)
        
        ttk.Button(control_frame, text="Stop Simulation", 
                  command=self.stop_simulation).pack(fill=tk.X, pady=2)
        
        ttk.Button(control_frame, text="Clear All Robots", 
                  command=self.clear_all_robots).pack(fill=tk.X, pady=2)
        
        # Right panel for simulation canvas
        right_panel = ttk.Frame(main_frame)
        right_panel.pack(side=tk.RIGHT, fill=tk.BOTH, expand=True)
        
        # Canvas for robot simulation
        canvas_frame = ttk.LabelFrame(right_panel, text="Robot Simulation Area", padding=5)
        canvas_frame.pack(fill=tk.BOTH, expand=True)
        
        self.canvas = tk.Canvas(canvas_frame, bg="white", width=800, height=600)
        self.canvas.pack(fill=tk.BOTH, expand=True)
        
        # Draw grid
        self.draw_grid()
        
        # Status bar
        self.status_var = tk.StringVar()
        self.status_var.set("Ready - Load robot configurations or add manual robots to begin")
        status_bar = ttk.Label(self.root, textvariable=self.status_var, relief=tk.SUNKEN, anchor=tk.W)
        status_bar.pack(side=tk.BOTTOM, fill=tk.X)
        
    def draw_grid(self):
        """Draw grid lines on canvas"""
        if not self.canvas:
            return
            
        self.canvas.delete("grid")
        width = self.canvas.winfo_width()
        height = self.canvas.winfo_height()
        
        # Draw grid lines every 50 pixels
        for i in range(0, width, 50):
            self.canvas.create_line(i, 0, i, height, fill="lightgray", tags="grid")
        for i in range(0, height, 50):
            self.canvas.create_line(0, i, width, i, fill="lightgray", tags="grid")
            
    def load_robot_config(self):
        """Load robot configuration from JSON file"""
        file_path = filedialog.askopenfilename(
            title="Select Robot Configuration File",
            filetypes=[("JSON files", "*.json"), ("All files", "*.*")],
            initialdir=os.path.join(os.path.dirname(__file__), "robot_configs") # Start in robot_configs
        )
        
        if not file_path:
            return
            
        try:
            with open(file_path, 'r') as f:
                config = json.load(f)
            
            # Extract robot info from the config
            if "data" in config and "user" in config["data"]:
                user_data = config["data"]["user"]
                robot_id = user_data.get("topic", "")
                
                # Check if a robot with this ID already exists
                if robot_id in self.robots:
                    messagebox.showwarning("Warning", f"Robot ID '{robot_id}' already exists. Skipping.")
                    return

                robot = Robot(
                    id=robot_id,
                    x=random.randint(100, 700),
                    y=random.randint(100, 500),
                    topic=user_data.get("topic", ""),
                    color=random.choice(["red", "green", "blue", "purple", "orange", "brown", "pink", "cyan"]),
                    aws_endpoint=AWS_IOT_ENDPOINT # Assign the global endpoint
                )
                
                self.robots[robot_id] = robot
                self.update_robot_list()
                self.draw_robots()
                
                self.status_var.set(f"Loaded robot: {robot_id} from {os.path.basename(file_path)}")
                
        except Exception as e:
            messagebox.showerror("Error", f"Failed to load robot config from {os.path.basename(file_path)}: {str(e)}")
            
    def add_manual_robot(self):
        """Add a robot manually and prompt for its topic"""
        robot_id = simpledialog.askstring("Robot ID", "Enter a unique ID for the new robot:", parent=self.root)
        if not robot_id:
            return
        
        if robot_id in self.robots:
            messagebox.showwarning("Warning", f"Robot ID '{robot_id}' already exists. Please choose a different one.")
            return

        topic = simpledialog.askstring("MQTT Topic", f"Enter the MQTT topic for '{robot_id}':", parent=self.root)
        if not topic:
            return

        robot = Robot(
            id=robot_id,
            x=random.randint(100, 700),
            y=random.randint(100, 500),
            topic=topic,
            status="disconnected", # Manual robots start disconnected
            aws_endpoint=AWS_IOT_ENDPOINT # Assign the global endpoint
        )
        
        self.robots[robot_id] = robot
        self.update_robot_list()
        self.draw_robots()
        
        self.status_var.set(f"Added manual robot: {robot_id} with topic: {topic}. Connect to activate.")
        
    def connect_all_robots(self):
        """Connect all robots to MQTT"""
        for robot_id, robot in self.robots.items():
            # Only attempt connection if endpoint is set and robot isn't already connected/connecting
            if robot.aws_endpoint != "YOUR_AWS_IOT_ENDPOINT" and robot.status in ["disconnected", "error"]:
                threading.Thread(target=self.connect_robot, args=(robot,), daemon=True).start()
            elif robot.status == "connected":
                print(f"Robot {robot.id} is already connected.")
            else:
                print(f"Robot {robot.id} has an invalid endpoint or credentials for connection.")
                
    def connect_robot(self, robot: Robot):
        """Connect a single robot to MQTT using certificates"""
        # Ensure only one connection attempt at a time for a robot
        if robot.mqtt_client and robot.status == "connected":
            return
            
        robot.status = "connecting..." # Indicate connection in progress
        self.update_robot_list()
        
        try:
            # Validate essential configuration
            if (robot.aws_endpoint == "YOUR_AWS_IOT_ENDPOINT" or not robot.topic):
                raise ValueError("AWS IoT endpoint or topic is not configured for this robot.")

            # Check if all certificate files exist
            for path in [ROOT_CA_PATH, PRIVATE_KEY_PATH, CERTIFICATE_PATH]:
                if not os.path.exists(path):
                    raise FileNotFoundError(f"Required certificate file not found: {path}")

            client_id = f"simulation_{robot.id}_{int(time.time())}"
            robot.mqtt_client = AWSIoTMQTTClient(client_id) # No useWebsocket=True here, as certificate auth is typically over TCP
            
            robot.mqtt_client.configureEndpoint(robot.aws_endpoint, 8883) # Default MQTT port for cert auth
            
            # Configure certificates for mutual TLS authentication
            robot.mqtt_client.configureCredentials(ROOT_CA_PATH, PRIVATE_KEY_PATH, CERTIFICATE_PATH)
            
            # Configure connection parameters
            robot.mqtt_client.configureAutoReconnectBackoffTime(1, 32, 20)
            robot.mqtt_client.configureOfflinePublishQueueing(-1)
            robot.mqtt_client.configureDrainingFrequency(2)
            robot.mqtt_client.configureConnectDisconnectTimeout(10)
            robot.mqtt_client.configureMQTTOperationTimeout(5)
            
            # Connect and subscribe
            robot.mqtt_client.connect()
            robot.mqtt_client.subscribe(robot.topic, 1, lambda client, userdata, message: self.mqtt_callback(robot, message))
            
            robot.status = "connected"
            self.update_robot_list()
            
            print(f"✅ Robot {robot.id} connected to topic: {robot.topic}")
            
        except FileNotFoundError as fnfe:
            robot.status = "error"
            self.update_robot_list()
            print(f"❌ Certificate File Error for robot {robot.id}: {str(fnfe)}")
            messagebox.showerror("Certificate Error", str(fnfe))
        except Exception as e:
            robot.status = "error"
            self.update_robot_list()
            print(f"❌ Failed to connect robot {robot.id}: {str(e)}")
            messagebox.showerror("Connection Error", f"Failed to connect robot {robot.id}: {str(e)}\n\nPlease ensure your AWS IoT endpoint is correct and certificate files are valid.")
            
    def mqtt_callback(self, robot: Robot, message):
        """Handle MQTT message for a robot"""
        try:
            payload = message.payload.decode()
            print(f"📩 Robot {robot.id} received: {payload}")
            
            # Update robot state
            robot.last_command = payload
            robot.last_command_time = time.time()
            
            # Parse command
            try:
                msg_data = json.loads(payload)
                print(f"Robot {robot.id} parsed command: {msg_data}")
                if msg_data.get("type") == "disconnect":
                    robot.status = "disconnected"
                    if robot.mqtt_client:
                        robot.mqtt_client.disconnect()
                        robot.mqtt_client = None
                    return
                    
                if msg_data.get("type") == "videocall_on":
                    robot.status = "video_call"
                    return
                    
                if msg_data.get("type") == "videocall_off":
                    robot.status = "connected"
                    return
                
                # Handle movement commands
                if msg_data.get("key") and msg_data.get("timestamp"):
                    duration = msg_data.get("duration", 0.2)
                    key = msg_data["key"]
                    
                    # Check if command is recent enough (2 seconds)
                    command_time = msg_data["timestamp"]
                    current_time_ms = int(time.time() * 1000)
                    time_diff = current_time_ms - command_time
                    
                    if time_diff > 2000:
                        print(f"Robot {robot.id}: Command '{key}' too old (diff: {time_diff}ms). Ignoring.")
                        return
                    
                    # Start movement
                    robot.is_moving = True
                    robot.movement_start_time = time.time()
                    robot.movement_duration = duration
                    
                    if key == "ArrowUp":
                        robot.movement_type = "forward"
                    elif key == "ArrowDown":
                        robot.movement_type = "backward"
                    elif key == "ArrowLeft":
                        robot.movement_type = "left"
                        robot.target_angle = robot.angle - 10  # Rotate left
                    elif key == "ArrowRight":
                        robot.movement_type = "right"
                        robot.target_angle = robot.angle + 10  # Rotate right
                    print(f"Robot {robot.id} started {robot.movement_type} movement.")
                        
            except json.JSONDecodeError:
                print(f"Robot {robot.id}: Received non-JSON payload: {payload}")
                pass  # Not JSON, ignore
                
        except Exception as e:
            print(f"⚠️ Error processing MQTT message for robot {robot.id}: {e}")
            
    def disconnect_all_robots(self):
        """Disconnect all robots from MQTT"""
        for robot in self.robots.values():
            if robot.mqtt_client:
                try:
                    robot.mqtt_client.disconnect()
                    robot.mqtt_client = None
                    robot.status = "disconnected"
                except Exception as e:
                    print(f"Error disconnecting robot {robot.id}: {e}")
                    
        self.update_robot_list()
        self.status_var.set("All robots disconnected")
        
    def clear_all_robots(self):
        """Clear all robots from simulation"""
        self.disconnect_all_robots()
        self.robots.clear()
        self.update_robot_list()
        self.canvas.delete("robot")
        self.status_var.set("All robots cleared")
        
    def update_robot_list(self):
        """Update the robot list display"""
        # Clear existing items
        for item in self.robot_tree.get_children():
            self.robot_tree.delete(item)
            
        # Add robots
        for robot_id, robot in self.robots.items():
            battery_str = f"{robot.battery_level:.1f}%"
            # Attempt to extract key from JSON, if not, show full payload
            try:
                if robot.last_command:
                    cmd_data = json.loads(robot.last_command)
                    last_cmd = cmd_data.get("key", cmd_data.get("type", "unknown"))
                else:
                    last_cmd = "N/A"
            except json.JSONDecodeError:
                last_cmd = robot.last_command # Show raw command if not JSON
            
            self.robot_tree.insert("", "end", text=robot_id, 
                                 values=(robot.status, battery_str, last_cmd))
                                 
    def start_simulation(self):
        """Start the simulation animation"""
        if self.running:
            return
            
        self.running = True
        self.animation_thread = threading.Thread(target=self.animation_loop, daemon=True)
        self.animation_thread.start()
        
        self.status_var.set("Simulation running...")
        
    def stop_simulation(self):
        """Stop the simulation animation"""
        if not self.running:
            return
        self.running = False
        self.animation_thread.join(timeout=1) # Wait for thread to finish
        if self.animation_thread.is_alive():
            print("Warning: Animation thread did not terminate gracefully.")
        self.status_var.set("Simulation stopped")
        
    def animation_loop(self):
        """Main animation loop"""
        while self.running:
            self.update_robot_positions()
            # Use root.after to schedule GUI updates on the main thread
            self.root.after(0, self.draw_robots)
            self.root.after(0, self.update_robot_list)
            time.sleep(0.05)  # Approximately 20 FPS
            
    def update_robot_positions(self):
        """Update robot positions based on movement commands"""
        current_time = time.time()
        
        for robot in self.robots.values():
            if robot.is_moving:
                elapsed = current_time - robot.movement_start_time
                
                # Check if movement should have finished
                if elapsed >= robot.movement_duration:
                    robot.is_moving = False
                    robot.movement_type = ""
                    # Ensure final position/angle is set after full duration for rotation
                    if robot.movement_type in ["left", "right"]:
                        robot.angle = robot.target_angle % 360
                    continue
                    
                # Calculate movement progress (linear for position, smooth for rotation)
                # This ensures continuous movement rather than only at the end of the duration
                
                # For linear movement (forward/backward), calculate based on a small time delta
                if robot.movement_type == "forward":
                    speed_pixels_per_sec = 100 / robot.movement_duration # Calculate speed based on desired distance/duration
                    distance_moved_in_frame = speed_pixels_per_sec * 0.05 # Assuming 0.05s per frame
                    
                    dx = distance_moved_in_frame * math.cos(math.radians(robot.angle))
                    dy = distance_moved_in_frame * math.sin(math.radians(robot.angle))
                    
                    new_x = robot.x + dx
                    new_y = robot.y + dy
                    
                    # Keep within canvas bounds (adjusting for robot size)
                    robot.x = max(20, min(self.canvas.winfo_width() - 20, new_x))
                    robot.y = max(20, min(self.canvas.winfo_height() - 20, new_y))
                    
                elif robot.movement_type == "backward":
                    speed_pixels_per_sec = 100 / robot.movement_duration
                    distance_moved_in_frame = speed_pixels_per_sec * 0.05
                    
                    dx = distance_moved_in_frame * math.cos(math.radians(robot.angle + 180))
                    dy = distance_moved_in_frame * math.sin(math.radians(robot.angle + 180))
                    
                    new_x = robot.x + dx
                    new_y = robot.y + dy
                    
                    robot.x = max(20, min(self.canvas.winfo_width() - 20, new_x))
                    robot.y = max(20, min(self.canvas.winfo_height() - 20, new_y))
                    
                elif robot.movement_type in ["left", "right"]:
                    # Interpolate rotation smoothly over the duration
                    # Calculate angle change for this frame based on total rotation and remaining time
                    
                    # Target total rotation for a "left" or "right" command is 10 degrees as defined
                    total_rotation_degrees = 10
                    
                    # Calculate how much angle should change in this frame (0.05s)
                    angle_change_per_frame = (total_rotation_degrees / robot.movement_duration) * 0.05
                    
                    if robot.movement_type == "left":
                        robot.angle -= angle_change_per_frame
                    else: # "right"
                        robot.angle += angle_change_per_frame
                        
                    # Normalize angle
                    robot.angle = robot.angle % 360
                    if robot.angle < 0:
                        robot.angle += 360
                        
            # Simulate battery drain for connected robots
            if robot.status == "connected" and robot.battery_level > 0:
                robot.battery_level -= 0.01  # Slow drain
                if robot.battery_level < 0:
                    robot.battery_level = 0
                
    def draw_robots(self):
        """Draw all robots on canvas"""
        self.canvas.delete("robot")
        
        for robot in self.robots.values():
            self.draw_robot(robot)
            
    def draw_robot(self, robot: Robot):
        """Draw a single robot on canvas"""
        x, y = robot.x, robot.y
        size = 20
        
        # Robot body (circle)
        self.canvas.create_oval(x - size, y - size, x + size, y + size, 
                              fill=robot.color, outline="black", width=2, tags="robot")
        
        # Direction indicator (arrow)
        arrow_length = size * 1.5
        end_x = x + arrow_length * math.cos(math.radians(robot.angle))
        end_y = y + arrow_length * math.sin(math.radians(robot.angle))
        
        self.canvas.create_line(x, y, end_x, end_y, 
                              fill="black", width=3, arrow=tk.LAST, tags="robot")
        
        # Robot ID label
        self.canvas.create_text(x, y + size + 15, text=robot.id, 
                              font=("Arial", 8), tags="robot")
        
        # Status indicator
        status_color = {
            "connected": "green",
            "disconnected": "red",
            "manual": "orange", # Manual implies not yet connected via AWS
            "connecting...": "yellow",
            "error": "red",
            "video_call": "blue"
        }.get(robot.status, "gray")
        
        self.canvas.create_oval(x + size - 5, y - size + 5, x + size + 5, y - size + 15,
                              fill=status_color, outline="black", tags="robot")
        
        # Battery indicator
        battery_width = 30
        battery_height = 8
        battery_x = x - battery_width // 2
        battery_y = y - size - 20
        
        # Battery outline
        self.canvas.create_rectangle(battery_x, battery_y, 
                                   battery_x + battery_width, battery_y + battery_height,
                                   outline="black", tags="robot")
        
        # Battery fill
        fill_width = int(battery_width * (robot.battery_level / 100))
        battery_color = "green" if robot.battery_level > 50 else "orange" if robot.battery_level > 20 else "red"
        
        if fill_width > 0:
            self.canvas.create_rectangle(battery_x, battery_y,
                                       battery_x + fill_width, battery_y + battery_height,
                                       fill=battery_color, outline="", tags="robot")
        
    def run(self):
        """Run the simulation"""
        self.root.protocol("WM_DELETE_WINDOW", self.on_closing)
        self.root.mainloop()
        
    def on_closing(self):
        """Handle application closing"""
        self.running = False
        self.disconnect_all_robots()
        # Give a small delay for threads to terminate
        time.sleep(0.1) 
        self.root.destroy()

if __name__ == "__main__":
    # Check for required dependencies
    try:
        from AWSIoTPythonSDK.MQTTLib import AWSIoTMQTTClient
    except ImportError:
        print("❌ AWSIoTPythonSDK not found. Please install it with:")
        print("pip install AWSIoTPythonSDK")
        exit(1)
    
    print("🚀 Starting Multi-Robot MQTT Control Simulation")
    print("🔔 IMPORTANT: Remember to replace 'YOUR_AWS_IOT_ENDPOINT' at the top of the 'robot_simulation.py' file.")
    print("\n📁 Ensure 'AmazonRootCA1.pem', 'private.pem.key', and 'device-certificate.pem.crt' are in the 'cert/' directory.")
    print("🔗 Click 'Load Robot Config' to add robots from JSON files.")
    print("🤖 Click 'Add Manual Robot' to add test robots and specify their MQTT topic.")
    print("▶️ Click 'Start Simulation' to begin the animation.")
    
    app = RobotSimulation()
    app.run()



    # robot/ap-southeast-2:e70e9d78-b157-cf3d-911d-269d9d94c9f5