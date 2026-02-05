# The Robot Waiter

### This project is part of a multi-repository system. Please refer to the following repositories for complete functionality: ###

- [Main Repository (Raspberry Pi Code)](https://github.com/cepdnaclk/e20-3yp-The_Robot_Waiter)
- [Robot interface(React)](https://github.com/cepdnaclk/3YP_RW_robot_interface)
- [Employee Backend (Node.js)](https://github.com/kushanmalintha/3YP_RW_employee-_backend)
- [Employee Interface (React)](https://github.com/kushanmalintha/3YP_RW_employee_interface)
- [Kitchen Backend (Node.js)](https://github.com/kushanmalintha/3YP_RW_kitchen_backend)
- [Project page](https://cepdnaclk.github.io/e20-3yp-The_Robot_Waiter/#)
##  Project Management

We manage and track our development process using a **Trello board**. Tasks are organized into categories such as:
You can view our full task board here:  
🔗 [Trello Board – 3YP RobotWaiter](https://trello.com/b/s9YXYOW1/3yp-robotwaiter)

---
## Team
- E/20/100, A.I. Fernando, [email](mailto:e20100@eng.pdn.ac.lk)
- E/20/243, K.M.K. Malintha, [email](mailto:e20243@eng.pdn.ac.lk)
- E/20/280, R.S. Pathirage, [email](mailto:e20280@eng.pdn.ac.lk)
- E/20/434, Wickramaarachchi P.A., [email](mailto:e20434@eng.pdn.ac.lk)
---
## Supervisors
- Dr. Isuru Nawinne, [email](isurunawinne@eng.pdn.ac.lk)
---

#### Table of Contents
1. [Introduction](#introduction)
2. [Solution Architecture](#solution-architecture)
3. [Hardware & Software Designs](#hardware-and-software-designs)
4. [Testing](#testing)
5. [Detailed Budget](#detailed-budget)
6. [Conclusion](#conclusion)
---

## Introduction

The Robot Waiter is a cloud controlled service robot designed to assist in the food and beverage industry. It operates via online connectivity, providing efficient delivery of items to customers without the need for automation. This solution bridges the gap between traditional manual service and fully automated systems, offering flexibility, cost-effectiveness, and ease of use.

![arch1](https://github.com/user-attachments/assets/d1182dd7-442a-4956-923d-862f7409d847)

---
### Automated charging dock for robot navigation

The robot utilizes OpenCV's ArUco marker detection as part of its autonomous navigation system. In the employee interface, a real-time video feed displays the restaurant environment as captured by the onboard camera. Within the restaurant, a charging dock is equipped with a visible ArUco marker. The robot detects this marker using computer vision and calculates its relative distance and orientation based on the visual input. This enables the robot to autonomously navigate towards the dock with precision, ensuring reliable and efficient recharging without human intervention.

<img width="996" height="570" alt="image" src="https://github.com/user-attachments/assets/707eec71-82d6-4821-a038-157797a780a7" />


# step by step

##   Step 1: Understand the Roles in the System
There are three main players in this system:

Admin – The boss. Controls everything.

Employee – Waiters or staff who control the robots.

Robot – The actual robot that does tasks (like delivering food).

##   Step 2: What the System is Made Of (Architecture)
The system is made of different parts that talk to each other:

A cloud database (Firebase) to store information.

A messaging system (AWS MQTT) to send robot commands.

A robot backend program (on Raspberry Pi) that listens and acts.

A web interface for employees and admin to log in and control things.

A temporary communication channel (WebSocket) used once to share robot info.

##   Step 3: Admin Sets Up the System
What Admin Can Do:
Signs up to the system (using email/password).

Adds employees – gives each one a username and password.

Registers new robots into the system (each gets a unique ID).

Sees a dashboard of robots and employees.

After this, the system is ready to be used.

##  Step 4: Employee Logs In
Employee goes to the website.

Logs in using the credentials given by the Admin.

Can now see a list of available robots.

##   Step 5: Robot is Powered On and Connects to Backend
When a robot is turned on:

The robot backend program (in Python) starts running on the robot.

It waits for a message from the cloud using AWS MQTT on the topic /connect.

It does nothing until an employee selects it.


##   Step 6: Robot Backend Receives the Connection Request
The robot:

Was listening to the /connect channel.

Now sees a message with its ID.

Once it sees this, it starts a WebSocket connection with the robot’s frontend interface.

##   Step 7: Robot Shares Its Info Temporarily via WebSocket
The robot and its frontend:

Can’t talk directly, so they use a WebSocket tunnel (temporary).

Through this tunnel, the robot shares its details (status, availability, etc.).

These details go to the Firebase database.

##   Step 8: Employee Selects a Robot
From their interface, the employee selects a robot from the list.

The selected robot's ID is sent to AWS MQTT to a special channel: /connect.

##   Step 9: WebSocket is Closed
After sharing its info, the WebSocket is closed.

From now on, Firebase stores the robot data.

Backend no longer talks to the frontend directly.

##   Step 10: System Enters Communication Mode (Live Control)
Now everything is set up for real-time control:

Robot:
Subscribes to a channel like robot/123/commands via AWS MQTT.

Waits for commands like “move forward”, “turn left”, etc.

Employee:
Is also connected to AWS MQTT.

Sends commands to the robot by publishing to the same topic (robot/123/commands).

This is how they “talk” to each other.

##   Step 11: Real-Time Interaction
Employee presses buttons on their interface (like a remote).

Each button sends a command through AWS MQTT.

Robot receives the command and moves accordingly.

##  Step 12: Repeat as Needed
The robot can update its status to Firebase.

Admin or employee can monitor it.

If a new robot is added, admin registers it again and the same process happens.

## Solution Architecture

The system's architecture integrates the following components:

- **User Interaction**: Users interact with the robot via an online platform, utilizing camera modules and touch displays for real-time feedback.
- **Navigation System**: Powered by DC motors, ultrasonic sensors, and a gyroscope for precise movement and obstacle detection.
- **Power System**: A 12V NiMH battery with a compatible charger ensures sustainable energy for operation.
- **Processing Unit**: The Raspberry Pi 3 B+ and ESP32 microcontroller handle computations and communication, ensuring seamless control.
- **Online Connectivity**: The robot leverages web-based control, allowing users to operate it from a remote location.

---

## Hardware and Software Designs

Detailed designs for the hardware and software components will include:
- Schematics for hardware assembly.
- Software modules for navigation, user interface, and connectivity.
- Integration between Raspberry Pi, ESP32, and sensors.

---

#  How to Physically Build the Robot – Step-by-Step Guide

![image](https://github.com/user-attachments/assets/4d39e56a-cc67-426a-8cd1-c3df733e01ac)

Parts You Need
Before we begin, make sure you have all these components:

### Mechanical/Structural Parts
4 rubber wheels

4 gear motors

Screws, nuts, and tools (screwdriver, drill if needed)

Wooden chassis box (main body)

2 wooden plates (top and bottom platforms)

Aluminium frame (for structure and support)

### Electronics
Raspberry Pi (central controller)

12V Li-ion battery

2 Motor Controllers (H-bridge or L298N-type)

Buck converter (to step down voltage to 5V)

Dot board (for wiring and mounting)

Display (screen – LCD, OLED or touchscreen)

Camera module (for vision)

2 Ultrasonic sensors (for obstacle detection)

🛠 Step-by-Step Assembly Procedure
##  Step 1: Prepare the Wooden Chassis
Take the wooden chassis box.

Ensure it's strong and balanced to hold all the components.

Drill holes for screws to mount motors and wheels.

##  Step 2: Mount the Motors and Wheels
Attach the 4 gear motors to the chassis using screws.

Connect one wheel to each motor.

Make sure the wheels are aligned straight and can rotate freely.

##  Step 3: Build the Frame
Attach the aluminium frame vertically on the chassis.

Fix the two wooden plates:

One near the bottom to hold the battery and electronics.

One on top to hold the display and camera.

##  Step 4: Add Power Supply
Place the 12V Li-ion battery securely inside the chassis.

Connect the buck converter to the battery to step down voltage to 5V for Raspberry Pi and sensors.

Ensure proper insulation to prevent short circuits.

##  Step 5: Mount the Raspberry Pi and Dot Board
Fix the Raspberry Pi securely on the lower platform.

Attach the dot board next to it (used for custom wiring).

Fix the 2 motor controllers on the dot board or chassis wall.

##  Step 6: Wire the Motors
Connect each pair of motors (left side and right side) to one motor controller.

Wire the motor controllers to the GPIO pins of Raspberry Pi through the dot board.

Connect the motor controllers’ power lines to the 12V battery.

##   Step 7: Install the Camera and Display
Mount the camera module on the top plate, facing forward.

Secure the display screen next to or above the camera.

Wire both to the Raspberry Pi using their respective connectors (camera via CSI, display via HDMI/GPIO).

##  Step 8: Add Ultrasonic Sensors
Attach 2 ultrasonic sensors to the front corners of the robot.

Face them outward for obstacle detection.

Wire them to the Raspberry Pi’s GPIO pins.

##  Step 9: Power and Safety Check
Double-check all wiring – make sure no wires are loose or shorted.

Secure all components using tape, brackets, or screws.

Connect the battery and check if the buck converter gives correct output (5V).

##  Step 10: Test the Robot
Turn on the system.

Make sure:

Raspberry Pi powers up.

Motors respond to test signals.

Camera and display work.

Ultrasonic sensors give distance readings.

##  Optional Step: Tidy the Wiring
Use zip ties or cable sleeves to clean up messy wires.

Label the connections if needed for easy debugging.

![image](https://github.com/user-attachments/assets/550c40c0-51c1-4966-874a-7f882166764b)


# Testing

Comprehensive testing of both hardware and software components:
- Navigation accuracy and obstacle detection.
- Responsiveness of user controls via the online interface.
- Battery performance under varying workloads.


##  hardware  testing

![image](https://github.com/user-attachments/assets/b65bf9e6-8bd5-48d7-9085-7080e9e1cb57)


## software testing

![sw test](https://github.com/user-attachments/assets/3cf160b9-eb79-4998-ae38-cb52762be329)


---

## Detailed Budget

| **Category**         | **Item**                 | **Description**                            | **Quantity** | **Unit Cost (LKR)** | **Total Cost (LKR)** |
|---------------------|--------------------------|--------------------------------------------|--------------|---------------------|-----------------------|
| **User Interaction**| Camera Module            | Raspberry Pi Camera Module 1               | 1            | 1800                | 1800                  |
|                     | Display                  | HDMI Display                               | 1            | 6000                | 6000                  |
| **Power System**    | Battery                  | 12V UPS Battery                            | 1            | 5000                | 5000                  |
|                     | Charger                  | 12V Charger                                | 1            | 2500                | 2500                  |
|                     | Buck Converter           | 12V to 5V Converter                        | 1            | 150                 | 150                   |
| **Navigation**      | Motors                   | JGB 520 100 RPM Gear Motors                | 4            | 1390                | 5560                  |
|                     | Wheels                   | Rubber Wheels                              | 4            | 190                 | 760                   |
|                     | Ultrasonic Sensors       | HC-SR04                                    | 2            | 500                 | 1000                  |
| **Structure**       | Tray Frame               | Aluminium Frame                            | 1            | 2000                | 2000                  |
|                     | Chassis                  | Wooden Chassis + Assembly Cost             | 1            | 1000                | 1000                  |
|                     | Lathe Works              | Axle Lathe Processing                      | 4            | 600                 | 2400                  |
| **Processing Unit** | Raspberry Pi 3 B         | 1.4GHz 64-bit Quad-Core Processor          | 1            | 20000               | 20000                 |

|                     |                          |                                            |              |                     | **Total: 49,970 LKR** |

---



## Conclusion

The Robot Waiter project aims to revolutionize the hospitality industry by providing a practical, remotely controlled robot capable of efficient service. Future developments could include integrating AI for automation, enhancing the robot's scalability, and exploring commercialization opportunities.

---


