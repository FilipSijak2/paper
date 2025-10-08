#!/usr/bin/env python3
from launch import LaunchDescription
from launch_ros.actions import Node
import os

def generate_launch_description():
    config_path = os.environ.get('SF_CONFIG', '/app/sensor_fusion.yaml')
    return LaunchDescription([
        Node(
            package='sensor_fusion_pkg',
            executable='arduino_listener',
            name='arduino_listener',
            output='screen',
            emulate_tty=True,
            parameters=[{'config_file': config_path}],
            arguments=[]
        )
    ])
