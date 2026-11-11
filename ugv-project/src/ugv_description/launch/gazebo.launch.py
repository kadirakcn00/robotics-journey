"""UGV'yi ROS 2 Humble + Gazebo Fortress ile baslatir.

Calistirma:
    ros2 launch ugv_description gazebo.launch.py
    ros2 launch ugv_description gazebo.launch.py rviz:=true
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    pkg_share = get_package_share_directory('ugv_description')
    ros_gz_sim_share = get_package_share_directory('ros_gz_sim')

    urdf_path = os.path.join(pkg_share, 'urdf', 'ugv.urdf')
    default_world = os.path.join(pkg_share, 'worlds', 'ugv_world.sdf')
    rviz_config = os.path.join(pkg_share, 'config', 'ugv.rviz')

    with open(urdf_path, 'r') as f:
        robot_description = f.read()

    world = LaunchConfiguration('world')
    rviz = LaunchConfiguration('rviz')

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
            '-z', '0.2',
        ],
    )

    # 4) ROS 2 <-> Gazebo topic koprusu
    #    [  : Gazebo -> ROS
    #    ]  : ROS -> Gazebo
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
        ],
        parameters=[{'use_sim_time': True}],
    )

    # 5) (Istege bagli) RViz2
    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        arguments=['-d', rviz_config],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(rviz),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'world', default_value=default_world,
            description='Gazebo world (.sdf) dosyasi'),
        DeclareLaunchArgument(
            'rviz', default_value='false',
            description='true ise RViz2 de acilir'),
        gazebo,
        robot_state_publisher,
        spawn,
        bridge,
        rviz_node,
    ])
