from launch import LaunchDescription
from launch_ros.actions import Node

def generate_launch_description():
    return LaunchDescription([
        Node(
            package='camera_stream',
            executable='camera_node',
            name='camera_stream_node',
            parameters=[{'udp_port': 5000}]
        )
    ])
