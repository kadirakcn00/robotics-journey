"""Navigasyon: simulasyon + Nav2 (AMCL + planner + controller) + RViz2.

Calistirma:
    ros2 launch ugv_bringup nav.launch.py
    ros2 launch ugv_bringup nav.launch.py map:=/tam/yol/harita.yaml

RViz2'de "2D Goal Pose" ile hedef ver, robot oraya otonom gider.
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, TimerAction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    gazebo_share = get_package_share_directory('ugv_gazebo')
    slam_share = get_package_share_directory('ugv_slam')
    nav_share = get_package_share_directory('ugv_navigation')
    nav2_bringup_share = get_package_share_directory('nav2_bringup')

    world = LaunchConfiguration('world')
    map_file = LaunchConfiguration('map')
    rviz = LaunchConfiguration('rviz')

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(gazebo_share, 'launch', 'sim.launch.py')),
        launch_arguments={'world': world}.items(),
    )

    # Gazebo, /clock ve TF hazir olsun diye Nav2 biraz gecikmeli baslar
    navigation = TimerAction(
        period=5.0,
        actions=[IncludeLaunchDescription(
            PythonLaunchDescriptionSource(
                os.path.join(nav_share, 'launch', 'navigation.launch.py')),
            launch_arguments={'map': map_file, 'use_sim_time': 'true'}.items(),
        )],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        arguments=['-d', os.path.join(nav2_bringup_share, 'rviz', 'nav2_default_view.rviz')],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(rviz),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'world',
            default_value=os.path.join(gazebo_share, 'worlds', 'ugv_world.sdf'),
            description='Gazebo world (.sdf) dosyasi'),
        DeclareLaunchArgument(
            'map',
            default_value=os.path.join(slam_share, 'maps', 'ugv_world.yaml'),
            description='Nav2 haritasi (.yaml)'),
        DeclareLaunchArgument('rviz', default_value='true',
                              description='true ise RViz2 de acilir'),
        sim,
        navigation,
        rviz_node,
    ])
