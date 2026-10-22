# M1: URDF (Robot Model)

**Environment:** Ubuntu 20.04 + ROS 2 Foxy  
**Project:** Four-wheeled ground robot (UGV)  
**File:** `~/Desktop/ros2_ws/src/ugv_project/ugv_description/urdf/ugv.urdf`

## 1. URDF

**Definition:** URDF is a format used to describe a robot's physical structure with XML. We use it to define the robot's parts, shapes, how the parts are connected, and which parts can move. All of this is written inside the `<robot>` tag.

```xml
<?xml version="1.0"?>
<robot name="ugv">

    <!-- Robot parts (links) go here -->

    <!-- Connections (joints) go here -->

</robot>
```

**Commands:**
```bash
cd ~/Desktop/ros2_ws/src/ugv_project/ugv_description/urdf
ls -l ugv.urdf
check_urdf ugv.urdf
```

- `ls -l ugv.urdf`: Checks that the file is there.
- `check_urdf ugv.urdf`: Checks whether the file can be read correctly. If it works, it prints `Successfully Parsed XML`.

**Real-life example:** Before a vehicle is put together in a factory, people plan which part goes where. URDF is like that plan for a robot.

**Note:** Passing `check_urdf` does not mean the design itself is correct. It only means the file can be read.

---

## 2. Link

**Definition:** A link is one part of a robot. Our robot has five links:

| Link | What it represents |
|---|---|
| `base_link` | Main body |
| `right_front_wheel` | Right front wheel |
| `right_back_wheel` | Right rear wheel |
| `left_front_wheel` | Left front wheel |
| `left_back_wheel` | Left rear wheel |

```xml
<link name="base_link">
</link>
```

An empty link is invisible. To give it a shape, we need to add `visual`.

**Commands:**
```bash
check_urdf ugv.urdf
grep -n '<link' ugv.urdf
```

`grep -n '<link' ugv.urdf` lists the link definitions in the file and shows their line numbers.

**Real-life example:** A toy car has a body and four wheels. In URDF, each of these is a separate link.

---

## 3. Visual, Geometry, Material

**Definition:** These tell RViz2 what the robot should look like.

- `visual`: How the part looks
- `geometry`: Its shape and size
- `material`: Its color

The chassis is a box, and the wheels are cylinders.

```xml
<visual>
    <geometry>
        <box size="0.5 0.3 0.2"/>
    </geometry>
</visual>
```

The values are in meters. In order, they mean length `0.5`, width `0.3`, and height `0.2`.

```xml
<visual>
    <geometry>
        <cylinder radius="0.07" length="0.04"/>
    </geometry>
</visual>
```

For the wheel, the radius is `0.07` and the thickness is `0.04`.

A cylinder stands upright by default. We change its direction to lay the wheel on its side:

```xml
<origin xyz="0 0 0" rpy="1.5708 0 0"/>
```

`1.5708` radians is about 90 degrees.

**Commands:**
```bash
grep -n -E 'visual|geometry|box|cylinder|material' ugv.urdf
```

This command shows the lines that contain the visual definitions.

**Real-life example:** This is like drawing the chassis as a rectangular box and the wheels as cylinders in a CAD program. For now, we use simple shapes. We can add more details with CAD later.

**Note:** If a wheel looks red in RViz2, that does not automatically mean there is an error. It may depend on the color settings.

---

## 4. Collision

**Definition:** `collision` defines the shape used when checking whether objects hit each other. It does not have to look exactly like the visible shape.

| Part | What it does |
|---|---|
| `visual` | Defines how the robot looks |
| `collision` | Defines how collisions are checked |

```xml
<collision>
    <geometry>
        <box size="0.5 0.3 0.2"/>
    </geometry>
</collision>
```

**Commands:**
```bash
grep -n -A8 '<collision>' ugv.urdf
```

This command shows the `collision` line and the eight lines below it.

**Real-life example:** A robot may have screw heads and small bumps on its body. Checking every tiny detail can make a simulation slower, so we may use one simple box to represent the body.

**Note:** Having `collision` does not mean we are ready for Gazebo yet. For physics, we also need mass (`inertial`) and a control system.

---

## 5. Joint

**Definition:** A joint is a connection between two links.

| Type | Meaning |
|---|---|
| `fixed` | Does not move |
| `revolute` | Turns within a limited angle range |
| `continuous` | Can turn all the way around |
| `prismatic` | Slides along one axis |

Our wheels use `continuous` joints.

```xml
<joint name="right_front_wheel_joint" type="continuous">
    <parent link="base_link"/>
    <child link="right_front_wheel"/>
    <origin xyz="0.16 -0.17 0.07" rpy="0 0 0"/>
    <axis xyz="0 1 0"/>
</joint>
```

- `name`: The joint's name
- `type`: How it can move
- `parent`: The main link it is attached to
- `child`: The link connected to it
- `origin`: Its position and direction
- `axis`: The axis it turns around

**Commands:**
```bash
grep -n -E '<joint|<parent|<child|<origin|<axis' ugv.urdf
```

This lists the lines related to joints.

**Real-life example:** A car wheel is attached to the body, but it can still turn around its own axis. A joint describes this connection.

---

## 6. Origin and Axis

**Definition:** `origin` tells us where a part is placed. `axis` tells us which axis a joint turns around.

```xml
<origin xyz="0.16 -0.17 0.07" rpy="0 0 0"/>
```

- `xyz`: Position (`x`, `y`, `z`), in meters
- `rpy`: Rotation (`roll`, `pitch`, `yaw`), in radians

```xml
<axis xyz="0 1 0"/>
```

This means the joint turns around the Y axis.

**Commands:**
```bash
grep -n -A5 '<joint' ugv.urdf
```

This command shows each joint and the five lines below it.

**Real-life example:** `origin` tells us how far the right front wheel is from the front, side, and bottom of the chassis. `axis` tells us which way the wheel turns.

**Origin sets the position and direction; axis sets the turning axis.**

---

## 7. Robot State Publisher

**Definition:** It uses the connection structure in the URDF to work out the position and direction of each link, then sends these updates through TF. When joint positions change, it updates the transformations too.

**Commands:**
```bash
ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(cat ugv.urdf)"
ros2 topic list
```

Run the first command in the folder where the URDF file is saved.

`ros2 topic list` shows the available topics.

**Real-life example:** On a real robot, wheel encoders measure how the wheels turn. These values can be used to work out the wheels' positions relative to the body. Robot State Publisher shares this information with other nodes.

**Note:** It does not run the motors. It only publishes the robot's structure and coordinate transformations.

---

## 8. Joint State Publisher GUI

**Definition:** This is a small window that lets us manually change joint values. We used it to test the wheels.

**Commands:**
```bash
ros2 run joint_state_publisher_gui joint_state_publisher_gui
ros2 topic echo /joint_states
```

The first command opens a window with sliders.

`ros2 topic echo /joint_states` shows the joint values in the terminal as we move the sliders.

**Real-life example:** We have not built the physical robot yet. We can use this window to change the wheel angles and check that the connections work, even without motors.

**Result:** When we move the sliders, the wheels turn in RViz2.

**Note:** This does not mean the robot moves across the ground. We are only seeing the joints move.

---

## 9. RViz2

**Definition:** RViz2 is a tool for showing the robot model and other robot-related information.

- `RobotModel`: The display that shows the robot from the URDF
- `Fixed Frame`: The coordinate frame used as the main reference for the view. We use `base_link`.

**Commands:**
```bash
rviz2
```

After it opens:

1. Click `Add`.
2. Add `RobotModel`.
3. Under `Global Options`, set `Fixed Frame` to `base_link`.
4. Check that the robot is visible.

We can also add the `TF` display to see the coordinate frames.

**Real-life example:** If we attach a camera to the robot's body, we can use RViz2 to see where the camera is compared with the body.

**Note:** RViz2 is not a physics simulator. It does not calculate gravity or friction.

---

## 10. Topics and TF

**Definition:** These are the topics we saw during this work:

| Topic | What it does |
|---|---|
| `/joint_states` | Gives joint position, speed, and effort information |
| `/robot_description` | Contains the robot's URDF description |
| `/tf` | Shares coordinate transformations that can change |
| `/tf_static` | Shares coordinate transformations that stay fixed |

**TF:** A system that keeps track of how the coordinate frames of the robot's parts relate to each other.

**Commands:**
```bash
ros2 topic list
ros2 topic echo /joint_states
ros2 topic info /joint_states
```

**Real-life example:** Imagine we put a camera on the front of the robot and an IMU on its body. If we know where the sensors are compared with the body, we can understand their data more correctly. TF keeps track of these positions and directions.

---

## 11. Wheel Positions

**Definition:** Each of the four wheels has its own link and joint. Their positions are measured relative to `base_link`.

| Wheel | Joint | `origin xyz` |
|---|---|---|
| Right front | `right_front_wheel_joint` | `0.16 -0.17 0.07` |
| Right rear | `right_back_wheel_joint` | `-0.16 -0.17 0.07` |
| Left front | `left_front_wheel_joint` | `0.16 0.17 0.07` |
| Left rear | `left_back_wheel_joint` | `-0.16 0.17 0.07` |

**Commands:**
```bash
grep -n -A5 '<joint' ugv.urdf
```

**Real-life example:** A car has two wheels at the front and two at the back. Here, we describe the same layout using numbers. If we change the values, the wheel positions change.

For now, the chassis is a simple box and does not have wheel wells. We will work on those later with CAD.

---

## 12. Starting the Project Again

**Definition:** We need three programs, and each one runs in a separate terminal. If you close one, that program stops.

1. `robot_state_publisher`: Publishes the transformations
2. `joint_state_publisher_gui`: Lets us change the joint angles
3. `rviz2`: Shows the robot

**Commands:**

First, open the URDF folder and check the file:

```bash
cd ~/Desktop/ros2_ws/src/ugv_project/ugv_description/urdf
check_urdf ugv.urdf
```

**Terminal 1:**
```bash
ros2 run robot_state_publisher robot_state_publisher --ros-args -p robot_description:="$(cat ugv.urdf)"
```

**Terminal 2:**
```bash
ros2 run joint_state_publisher_gui joint_state_publisher_gui
```

**Terminal 3:**
```bash
rviz2
```

Remember to run this in each new terminal first:

```bash
source /opt/ros/foxy/setup.bash
```

**Real-life example:** When testing robot software, the program that describes the robot, the program that sends joint values, and the program that displays the model each have a different job. Starting each one correctly helps us repeat the test.

---

