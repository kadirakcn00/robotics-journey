"""Simulasyon: Gazebo Fortress + UGV + kopru (+ RViz2).

Calistirma:
    ros2 launch ugv_bringup sim.launch.py
    ros2 launch ugv_bringup sim.launch.py rviz:=false
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
    bringup_share = get_package_share_directory('ugv_bringup')
    gazebo_share = get_package_share_directory('ugv_gazebo')

    world = LaunchConfiguration('world')
    rviz = LaunchConfiguration('rviz')

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_share, 'launch', 'sim.launch.py')),
        launch_arguments={'world': world}.items(),
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        arguments=['-d', os.path.join(bringup_share, 'config', 'sim.rviz')],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(rviz),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'world',
            default_value=os.path.join(gazebo_share, 'worlds', 'ugv_world.sdf'),
            description='Gazebo world (.sdf) dosyasi'),
        DeclareLaunchArgument('rviz', default_value='true',
                              description='true ise RViz2 de acilir'),
        sim,
        rviz_node,
    ])
