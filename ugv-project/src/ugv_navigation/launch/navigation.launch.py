"""Nav2'yi (map_server + AMCL + planner + controller ...) bizim ayarlarimizla baslatir.

Genelde ugv_bringup icinden cagrilir:
    ros2 launch ugv_bringup nav.launch.py

Argumanlar:
    map          : harita .yaml dosyasi (varsayilan: ugv_slam/maps/ugv_world.yaml)
    params_file  : Nav2 parametre dosyasi
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    nav_share = get_package_share_directory('ugv_navigation')
    slam_share = get_package_share_directory('ugv_slam')
    nav2_bringup_share = get_package_share_directory('nav2_bringup')

    map_file = LaunchConfiguration('map')
    params_file = LaunchConfiguration('params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')

    nav2 = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(
            os.path.join(nav2_bringup_share, 'launch', 'bringup_launch.py')),
        launch_arguments={
            'map': map_file,
            'params_file': params_file,
            'use_sim_time': use_sim_time,
            'autostart': 'true',
        }.items(),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'map',
            default_value=os.path.join(slam_share, 'maps', 'ugv_world.yaml'),
            description='Harita .yaml dosyasi'),
        DeclareLaunchArgument(
            'params_file',
            default_value=os.path.join(nav_share, 'config', 'nav2_params.yaml'),
            description='Nav2 parametre dosyasi'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        nav2,
    ])
