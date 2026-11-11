"""slam_toolbox'u (online async) bizim ayarlarimizla baslatir.

Genelde ugv_bringup icinden cagrilir:
    ros2 launch ugv_bringup slam.launch.py
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def generate_launch_description():
    slam_share = get_package_share_directory('ugv_slam')
    default_params = os.path.join(slam_share, 'config', 'slam_params.yaml')

    params_file = LaunchConfiguration('slam_params_file')
    use_sim_time = LaunchConfiguration('use_sim_time')

    slam = Node(
        package='slam_toolbox',
        executable='async_slam_toolbox_node',
        name='slam_toolbox',
        output='screen',
        parameters=[params_file, {'use_sim_time': use_sim_time}],
    )

    return LaunchDescription([
        DeclareLaunchArgument('slam_params_file', default_value=default_params,
                              description='slam_toolbox parametre dosyasi'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        slam,
    ])
