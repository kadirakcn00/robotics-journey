"""Gazebo Fortress'i acar, UGV'yi ekler ve ROS 2 <-> Gazebo koprusunu kurar.

Genelde dogrudan degil, ugv_bringup icinden cagrilir:
    ros2 launch ugv_bringup sim.launch.py

Argumanlar:
    world  : .sdf dunya dosyasi (varsayilan: ugv_world.sdf)
    x y z yaw : robotun baslangic konumu
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (AppendEnvironmentVariable, DeclareLaunchArgument,
                            IncludeLaunchDescription)
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import Command, LaunchConfiguration
from launch_ros.actions import Node
from launch_ros.parameter_descriptions import ParameterValue


PAN_CMD = '/model/ugv/joint/aim_pan_joint/0/cmd_pos'
TILT_CMD = '/model/ugv/joint/aim_tilt_joint/0/cmd_pos'


def generate_launch_description():
    description_share = get_package_share_directory('ugv_description')
    gazebo_share = get_package_share_directory('ugv_gazebo')
    ros_gz_sim_share = get_package_share_directory('ros_gz_sim')

    xacro_file = os.path.join(description_share, 'urdf', 'ugv.urdf.xacro')
    default_world = os.path.join(gazebo_share, 'worlds', 'ugv_world.sdf')

    world = LaunchConfiguration('world')
    x = LaunchConfiguration('x')
    y = LaunchConfiguration('y')
    z = LaunchConfiguration('z')
    yaw = LaunchConfiguration('yaw')

    robot_description = ParameterValue(
        Command(['xacro ', xacro_file]), value_type=str)

    # 0) model:// adreslerinin (tabelalar, hedef) bulunabilmesi icin model klasoru
    model_path = AppendEnvironmentVariable(
        'IGN_GAZEBO_RESOURCE_PATH', os.path.join(gazebo_share, 'models'))

    # 1) Gazebo Fortress (-r: simulasyonu baslat)
    gazebo = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(ros_gz_sim_share, 'launch', 'gz_sim.launch.py')),
        launch_arguments={'gz_args': ['-r ', world]}.items(),
    )

    # 2) URDF'i /robot_description'a yayinlar ve TF agacini olusturur
    robot_state_publisher = Node(
        package='robot_state_publisher',
        executable='robot_state_publisher',
        output='screen',
        parameters=[{
            'robot_description': robot_description,
            'use_sim_time': True,
        }],
    )

    # 3) Robotu /robot_description topic'inden Gazebo'ya ekler
    spawn = Node(
        package='ros_gz_sim',
        executable='create',
        output='screen',
        arguments=[
            '-name', 'ugv',
            '-topic', 'robot_description',
            '-x', x, '-y', y, '-z', z, '-Y', yaw,
        ],
    )

    # 4) ROS 2 <-> Gazebo topic koprusu
    #    [  : Gazebo -> ROS      ]  : ROS -> Gazebo
    bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        output='screen',
        arguments=[
            '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
            '/cmd_vel@geometry_msgs/msg/Twist]ignition.msgs.Twist',
            '/odom@nav_msgs/msg/Odometry[ignition.msgs.Odometry',
            '/tf@tf2_msgs/msg/TFMessage[ignition.msgs.Pose_V',
            '/scan@sensor_msgs/msg/LaserScan[ignition.msgs.LaserScan',
            '/joint_states@sensor_msgs/msg/JointState[ignition.msgs.Model',
            # Kameralar
            '/camera/front/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image',
            '/camera/front/camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo',
            '/camera/rear/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image',
            '/camera/rear/camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo',
            '/camera/aim/image_raw@sensor_msgs/msg/Image[ignition.msgs.Image',
            '/camera/aim/camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo',
            # Nisan tareti pozisyon komutlari
            PAN_CMD + '@std_msgs/msg/Float64]ignition.msgs.Double',
            TILT_CMD + '@std_msgs/msg/Float64]ignition.msgs.Double',
        ],
        # Gazebo'daki uzun topic adlarini ROS tarafinda kisaltir
        remappings=[(PAN_CMD, '/aim/pan_cmd'), (TILT_CMD, '/aim/tilt_cmd')],
        parameters=[{'use_sim_time': True}],
    )

    return LaunchDescription([
        DeclareLaunchArgument('world', default_value=default_world,
                              description='Gazebo world (.sdf) dosyasi'),
        DeclareLaunchArgument('x', default_value='0.0'),
        DeclareLaunchArgument('y', default_value='0.0'),
        DeclareLaunchArgument('z', default_value='0.2'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        model_path,
        gazebo,
        robot_state_publisher,
        spawn,
        bridge,
    ])
