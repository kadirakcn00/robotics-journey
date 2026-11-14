"""TEKNOFEST 2026 IKA parkuru: parkur dunyasi + su fizigi + kayar engel + kameralar.

Calistirma:
    ros2 launch ugv_bringup course.launch.py
    ros2 launch ugv_bringup course.launch.py start:=accel     # hizlanma parkurundan basla

Manuel kosu (surucu konsolu: kameralar + klavye + taret + lazer):
    ros2 launch ugv_bringup course.launch.py driver:=true

Parkur fizik testi (robot parkuru kendisi surer, takildigi asamayi raporlar):
    ros2 launch ugv_bringup course.launch.py tester:=true
    ros2 launch ugv_bringup course.launch.py tester:=true start:=accel   # hizlanma kosusu

Hiz komutu su fizigi node'undan gecer: /cmd_vel -> water_physics -> /cmd_vel_gz -> Gazebo
"""

import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import (AppendEnvironmentVariable, DeclareLaunchArgument,
                            IncludeLaunchDescription, OpaqueFunction)
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node

# Baslangic noktalari: (x, y, yaw)
STARTS = {
    'main': (7.5, 0.0, 3.14159265),    # ana parkur, A sirasi, -x yonune bakar
    'accel': (-0.4, 9.5, 0.0),         # hizlanma parkuru, +x yonune bakar (onu cizginin gerisinde)
}


def launch_setup(context):
    bringup_share = get_package_share_directory('ugv_bringup')
    gazebo_share = get_package_share_directory('ugv_gazebo')
    course_share = get_package_share_directory('ugv_course')

    start = LaunchConfiguration('start').perform(context)
    if start not in STARTS:
        raise RuntimeError(f'start "{start}" bilinmiyor, secenekler: {list(STARTS)}')
    x, y, yaw = STARTS[start]

    sim = IncludeLaunchDescription(
        PythonLaunchDescriptionSource(os.path.join(gazebo_share, 'launch', 'sim.launch.py')),
        launch_arguments={
            'world': os.path.join(course_share, 'worlds', 'teknofest_course.sdf'),
            'x': str(x), 'y': str(y), 'z': '0.05', 'yaw': str(yaw),
            'cmd_vel_topic': '/cmd_vel_gz',
        }.items(),
    )

    water = Node(
        package='ugv_course',
        executable='water_physics',
        name='water_physics',
        output='screen',
        parameters=[os.path.join(course_share, 'config', 'water_zones.yaml'),
                    {'use_sim_time': True, 'spawn_x': x, 'spawn_y': y, 'spawn_yaw': yaw}],
    )

    slider = Node(
        package='ugv_course',
        executable='sliding_obstacle',
        name='sliding_obstacle',
        output='screen',
        parameters=[{'use_sim_time': True}],
    )

    slider_bridge = Node(
        package='ros_gz_bridge',
        executable='parameter_bridge',
        name='bridge_course',
        output='screen',
        arguments=['/course/slider_cmd@std_msgs/msg/Float64]ignition.msgs.Double'],
        parameters=[{'use_sim_time': True}],
    )

    perception = LaunchConfiguration('perception')
    sign_detector = Node(
        package='ugv_perception',
        executable='sign_detector',
        name='sign_detector',
        namespace='perception/front',
        output='screen',
        parameters=[{'image_topic': '/camera/front/image_raw', 'use_sim_time': True}],
        condition=IfCondition(perception),
    )
    target_detector = Node(
        package='ugv_perception',
        executable='target_detector',
        name='target_detector',
        namespace='perception/aim',
        output='screen',
        parameters=[{'image_topic': '/camera/aim/image_raw', 'use_sim_time': True}],
        condition=IfCondition(perception),
    )

    driver = Node(
        package='ugv_teleop',
        executable='driver_station',
        name='driver_station',
        output='screen',
        condition=IfCondition(LaunchConfiguration('driver')),
    )

    tester = Node(
        package='ugv_course',
        executable='course_tester',
        name='course_tester',
        output='screen',
        parameters=[os.path.join(course_share, 'config', 'course_path.yaml'),
                    {'use_sim_time': True, 'run': start}],
        condition=IfCondition(LaunchConfiguration('tester')),
    )

    rviz = Node(
        package='rviz2',
        executable='rviz2',
        output='screen',
        arguments=['-d', os.path.join(bringup_share, 'config', 'perception.rviz')],
        parameters=[{'use_sim_time': True}],
        condition=IfCondition(LaunchConfiguration('rviz')),
    )

    return [
        # Parkur modelleri (koni, kayar engel, egimli zemin parcalari) icin model klasoru
        AppendEnvironmentVariable('IGN_GAZEBO_RESOURCE_PATH',
                                  os.path.join(course_share, 'models')),
        sim, water, slider, slider_bridge, sign_detector, target_detector, driver, tester,
        rviz,
    ]


def generate_launch_description():
    return LaunchDescription([
        DeclareLaunchArgument('start', default_value='main',
                              description='Baslangic: main (ana parkur) ya da accel'),
        DeclareLaunchArgument('perception', default_value='true',
                              description='Tabela okuyucu ve hedef bulucuyu calistir'),
        DeclareLaunchArgument('rviz', default_value='true'),
        DeclareLaunchArgument('driver', default_value='false',
                              description='true: surucu konsolunu ac (manuel kosu)'),
        DeclareLaunchArgument('tester', default_value='false',
                              description='true: parkur test surucusu robotu kendisi surer'),
        OpaqueFunction(function=launch_setup),
    ])
