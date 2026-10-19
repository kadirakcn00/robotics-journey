from launch import LaunchDescription 
from launch_ros.actions import Node

def generate_launch_description():
	return LaunchDescription([
	Node(
		 package='py_pubsub',
		 executable='my_talker',
		 name='talker',
		 output='screen',
	),
	Node(
                 package='py_pubsub',
                 executable='my_listener',
                 name='talker',
                 output='screen',	
	),

	])
