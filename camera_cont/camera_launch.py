#!/usr/bin/env python3
"""Custom launch file for Raspberry Pi Camera Module 3 in container.

Publishes:
  /camera/image_raw
  /camera/camera_info

Parameters you can override via ROS arguments or by editing this file.
"""
from launch import LaunchDescription
from launch_ros.actions import Node
from launch.actions import DeclareLaunchArgument
from launch.substitutions import LaunchConfiguration


def generate_launch_description():
    width_arg = DeclareLaunchArgument('width', default_value='1280')
    height_arg = DeclareLaunchArgument('height', default_value='720')
    fps_arg = DeclareLaunchArgument('fps', default_value='30')
    frame_id_arg = DeclareLaunchArgument('frame_id', default_value='rpi_cam_optical_frame')
    camera_info_url_arg = DeclareLaunchArgument('camera_info_url', default_value='file:///app/camera_info.yaml')

    params = [{
        'width': LaunchConfiguration('width'),
        'height': LaunchConfiguration('height'),
        'fps': LaunchConfiguration('fps'),
        'frame_id': LaunchConfiguration('frame_id'),
        'camera_info_url': LaunchConfiguration('camera_info_url'),
        # Common useful controls (uncomment / adjust as needed)
        # 'brightness': 0.5,
        # 'awb_mode': 'auto',
        # 'exposure_mode': 'normal',
    }]

    camera_node = Node(
        package='rpicam_ros',
        executable='rpicam_node',
        name='rpi_camera',
        namespace='camera',
        parameters=params,
        remappings=[
            ('image_raw', '/camera/image_raw'),
            ('camera_info', '/camera/camera_info')
        ]
    )

    return LaunchDescription([
        width_arg,
        height_arg,
        fps_arg,
        frame_id_arg,
        camera_info_url_arg,
        camera_node
    ])
