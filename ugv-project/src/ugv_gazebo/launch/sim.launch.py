"""Gazebo Fortress'i acar, UGV'yi ekler ve ROS 2 <-> Gazebo koprusunu kurar.

Genelde dogrudan degil, ugv_bringup icinden cagrilir:
    ros2 launch ugv_bringup sim.launch.py

Argumanlar:
    world  : .sdf dunya dosyasi (varsayilan: ugv_world.sdf)
    x y z yaw : robotun baslangic konumu
    cmd_vel_topic : Gazebo'daki DiffDrive'in dinledigi hiz topic'i (varsayilan /cmd_vel).
                    Parkurda su fizigi node'u araya girdigi icin /cmd_vel_gz verilir.
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
    cmd_vel_topic = LaunchConfiguration('cmd_vel_topic')

    robot_description = ParameterValue(
        Command(['xacro ', xacro_file, ' cmd_vel_topic:=', cmd_vel_topic]), value_type=str)

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

    # 4) ROS 2 <-> Gazebo topic kopruleri
    #    [  : Gazebo -> ROS      ]  : ROS -> Gazebo
    #    Uc ayri kopru: birinde sorun cikarsa digerleri (ozellikle saat, TF ve LIDAR)
    #    calismaya devam eder.
    def bridge(name, topics):
        return Node(
            package='ros_gz_bridge',
            executable='parameter_bridge',
            name=name,
            output='screen',
            arguments=topics,
            parameters=[{'use_sim_time': True}],
        )

    core_bridge = bridge('bridge_core', [
        '/clock@rosgraph_msgs/msg/Clock[ignition.msgs.Clock',
        [cmd_vel_topic, '@geometry_msgs/msg/Twist]ignition.msgs.Twist'],
        '/odom@nav_msgs/msg/Odometry[ignition.msgs.Odometry',
        '/ground_truth/odom@nav_msgs/msg/Odometry[ignition.msgs.Odometry',
        '/tf@tf2_msgs/msg/TFMessage[ignition.msgs.Pose_V',
        '/scan@sensor_msgs/msg/LaserScan[ignition.msgs.LaserScan',
        '/joint_states@sensor_msgs/msg/JointState[ignition.msgs.Model',
        '/imu@sensor_msgs/msg/Imu[ignition.msgs.IMU',
    ])

    camera_bridge = bridge('bridge_cameras', [
        f'/camera/{cam}/{kind}'
        for cam in ('front', 'rear', 'aim')
        for kind in ('image_raw@sensor_msgs/msg/Image[ignition.msgs.Image',
                     'camera_info@sensor_msgs/msg/CameraInfo[ignition.msgs.CameraInfo')
    ])

    # Nisan tareti pozisyon komutlari (topic adlari aim_turret.xacro'da verilir)
    turret_bridge = bridge('bridge_turret', [
        '/aim/pan_cmd@std_msgs/msg/Float64]ignition.msgs.Double',
        '/aim/tilt_cmd@std_msgs/msg/Float64]ignition.msgs.Double',
    ])

    return LaunchDescription([
        DeclareLaunchArgument('world', default_value=default_world,
                              description='Gazebo world (.sdf) dosyasi'),
        DeclareLaunchArgument('x', default_value='0.0'),
        DeclareLaunchArgument('y', default_value='0.0'),
        DeclareLaunchArgument('z', default_value='0.2'),
        DeclareLaunchArgument('yaw', default_value='0.0'),
        DeclareLaunchArgument('cmd_vel_topic', default_value='/cmd_vel'),
        model_path,
        gazebo,
        robot_state_publisher,
        spawn,
        core_bridge,
        camera_bridge,
        turret_bridge,
    ])
