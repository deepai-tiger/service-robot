# process_manager.py
import subprocess
import sys
import os
import signal
import time
from config_manager import ROBOT_CREDENTIALS_FILE, MQTT_LOG_FILE, WEBSOCKET_DATA_FILE, save_system_state, load_system_state

# Global variables for process management
motor_process = None
system_state = {"connected": False, "processes": []}

def start_robot_control():
    """Start the robot control script"""
    global motor_process, system_state
    try:
        print("🤖 Starting robot control script...")
        # Start the robot control script as a subprocess
        motor_process = subprocess.Popen([sys.executable, "motor_thread.py"])
        system_state["connected"] = True
        system_state["processes"] = [motor_process.pid]
        save_system_state(system_state)
        
        print("✅ Robot control script started successfully")
        return True
    except Exception as e:
        print(f"❌ Failed to start robot control script: {e}")
        return False

def stop_robot_control():
    """Stop all robot control processes"""
    global motor_process, system_state
    try:
        print("🛑 Stopping robot control processes...")
        
        if motor_process and motor_process.poll() is None:
            # Send termination signal to motor process
            motor_process.terminate()
            try:
                motor_process.wait(timeout=10)  # Wait up to 10 seconds
            except subprocess.TimeoutExpired:
                print("⚠️ Process didn't terminate gracefully, forcing kill...")
                motor_process.kill()
                motor_process.wait()
        
        # Clean up any remaining processes
        for pid in system_state.get("processes", []):
            try:
                os.kill(pid, signal.SIGTERM)
                time.sleep(1)
                os.kill(pid, signal.SIGKILL)  # Force kill if still running
            except ProcessLookupError:
                pass  # Process already terminated
            except Exception as e:
                print(f"⚠️ Error terminating process {pid}: {e}")
        
        # Clear credentials and state
        if os.path.exists(ROBOT_CREDENTIALS_FILE):
            os.remove(ROBOT_CREDENTIALS_FILE)
        if os.path.exists(MQTT_LOG_FILE):
            os.remove(MQTT_LOG_FILE)
        if os.path.exists(WEBSOCKET_DATA_FILE):
            os.remove(WEBSOCKET_DATA_FILE)
            
        system_state = {"connected": False, "processes": []}
        save_system_state(system_state)
        
        motor_process = None
        print("✅ Robot control stopped and cleaned up")
        return True
        
    except Exception as e:
        print(f"❌ Error stopping robot control: {e}")
        return False

def restart_robot_control():
    """Restart robot control using existing credentials"""
    try:
        if not os.path.exists(ROBOT_CREDENTIALS_FILE):
            print("❌ No existing credentials found for restart")
            return False
            
        print("🔄 Restarting robot control with existing credentials...")
        return start_robot_control()
        
    except Exception as e:
        print(f"❌ Error restarting robot control: {e}")
        return False

def wait_for_system_commands(driver):
    """Wait for disconnect/reconnect commands or manual interrupt"""
    global motor_process, system_state
    
    try:
        print("\n🎯 Monitoring system state...")
        print("💡 System will respond to MQTT disconnect/reconnect commands")
        print("🛑 Press Ctrl+C to manually stop the system")
        
        while True:
            # Check if motor process is still running
            if motor_process and motor_process.poll() is not None:
                print("⚠️ Motor process terminated unexpectedly")
                break
            
            # Check for system state changes
            current_state = load_system_state()
            
            if not current_state.get("connected", False):
                print("📡 Disconnect command received via MQTT")
                # Close browser and restart entire process
                print("🔒 Closing browser for full restart...")
                try:
                    driver.quit()
                except:
                    pass
                return False  # This will cause main() to restart the entire process
            
            time.sleep(5)  # Check every 5 seconds
            
    except KeyboardInterrupt:
        print("\n🛑 Manual shutdown requested")
        stop_robot_control()
        return True
    
    except Exception as e:
        print(f"❌ Error in system monitoring: {e}")
        return False
    
    return True