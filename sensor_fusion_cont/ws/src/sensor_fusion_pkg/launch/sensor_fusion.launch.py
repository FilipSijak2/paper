#!/usr/bin/env python3
import os

from launch import LaunchDescription
from launch_ros.actions import Node


def resolve_imu_source() -> str:
    raw_source = os.environ.get('SF_IMU_SOURCE', 'realsense').strip().lower()
    if raw_source in {'realsense', 'camera', 'd455'}:
        return 'realsense'
    return 'arduino'


def build_ekf_node() -> Node:
    ekf_config_path = os.environ.get('SF_EKF_CONFIG', '/app/robot_localization.yaml')
    return Node(
        package='robot_localization',
        executable='ekf_node',
        name='ekf_filter_node',
        output='screen',
        emulate_tty=True,
        parameters=[ekf_config_path],
    )


def generate_launch_description():
    config_path = os.environ.get('SF_CONFIG', '/app/sensor_fusion.yaml')
    imu_source = resolve_imu_source()
    ekf_node = build_ekf_node()

    if imu_source == 'realsense':
        input_topic = os.environ.get('SF_IMU_INPUT_TOPIC', '/camera/realsense/imu')
        output_topic = os.environ.get('SF_IMU_OUTPUT_TOPIC', '/imu/data')
        return LaunchDescription([
            Node(
                package='imu_filter_madgwick',
                executable='imu_filter_madgwick_node',
                name='camera_imu_filter',
                output='screen',
                emulate_tty=True,
                parameters=[{
                    'use_mag': False,
                    'publish_tf': False,
                }],
                remappings=[
                    ('imu/data_raw', input_topic),
                    ('imu/data', output_topic),
                ],
            ),
            Node(
                package='sensor_fusion_pkg',
                executable='realsense_imu_transform',
                name='realsense_imu_transform',
                output='screen',
                emulate_tty=True,
            ),
            ekf_node,
        ])

    raw_topic = os.environ.get('SF_IMU_RAW_TOPIC', '/imu/data_raw')
    output_topic = os.environ.get('SF_IMU_OUTPUT_TOPIC', '/imu/data')
    return LaunchDescription([
        Node(
            package='sensor_fusion_pkg',
            executable='arduino_listener',
            name='arduino_listener',
            output='screen',
            emulate_tty=True,
            parameters=[{'config_file': config_path}],
            arguments=[]
        ),
        Node(
            package='imu_filter_madgwick',
            executable='imu_filter_madgwick_node',
            name='arduino_imu_filter',
            output='screen',
            emulate_tty=True,
            parameters=[{
                'use_mag': False,
                'publish_tf': False,
            }],
            remappings=[
                ('imu/data_raw', raw_topic),
                ('imu/data', output_topic),
            ],
        ),
        ekf_node,
    ])
