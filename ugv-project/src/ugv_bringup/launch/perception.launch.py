"""Kamera ve algilama: test dunyasi + tabela/hedef tespiti + RViz2 (kamera goruntuleri).

Calistirma:
    ros2 launch ugv_bringup perception.launch.py

Topic'ler:
    /perception/front/stage_sign  (std_msgs/Int32)       on kameradaki tabela numarasi
    /perception/rear/stage_sign   (std_msgs/Int32)       geri kameradaki tabela numarasi
    /perception/aim/target        (geometry_msgs/PointStamped)  hedefin nisangaha gore sapmasi

Nisan taretini cevirmek icin (radyan):
    ros2 topic pub -1 /aim/pan_cmd std_msgs/msg/Float64 "{data: 0.3}"
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

    def sign_detector(camera):
        return Node(
            package='ugv_perception',
            executable='sign_detector',
            name='sign_detector',
            namespace=f'perception/{camera}',
            output='screen',
            parameters=[{'image_topic': f'/camera/{camera}/image_raw',
                         'use_sim_time': True}],
        )

    target_detector = Node(
        package='ugv_perception',
        executable='target_detector',
        name='target_detector',
        namespace='perception/aim',
        output='screen',
        parameters=[{'image_topic': '/camera/aim/image_raw', 'use_sim_time': True}],
    )

    rviz_node = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        arguments=['-d', os.path.join(bringup_share, 'config', 'perception.rviz')],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(rviz),
    )

    return LaunchDescription([
        DeclareLaunchArgument(
            'world',
            default_value=os.path.join(gazebo_share, 'worlds', 'perception_world.sdf'),
            description='Gazebo world (.sdf) dosyasi'),
        DeclareLaunchArgument('rviz', default_value='true',
                              description='true ise RViz2 de acilir'),
        sim,
        sign_detector('front'),
        sign_detector('rear'),
        target_detector,
        rviz_node,
    ])
