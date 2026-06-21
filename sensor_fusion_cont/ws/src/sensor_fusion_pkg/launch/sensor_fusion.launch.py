#!/usr/bin/env python3
import os

from launch import LaunchDescription
from launch_ros.actions import Node


def env_bool(name: str, default: str = 'false') -> bool:
    return os.environ.get(name, default).strip().lower() in {'1', 'true', 'yes', 'on'}


def env_float(name: str, default: float) -> float:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return float(raw_value)
    except ValueError:
        return default


def env_int(name: str, default: int) -> int:
    raw_value = os.environ.get(name)
    if raw_value is None:
        return default
    try:
        return int(raw_value)
    except ValueError:
        return default


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


def build_imu_yaw_rate_corrector_node() -> Node:
    return Node(
        package='sensor_fusion_pkg',
        executable='imu_yaw_rate_corrector',
        name='imu_yaw_rate_corrector',
        output='screen',
        emulate_tty=True,
        parameters=[{
            'input_topic': os.environ.get('SF_IMU_CORRECTOR_INPUT_TOPIC', '/imu/base_link'),
            'output_topic': os.environ.get(
                'SF_IMU_CORRECTOR_OUTPUT_TOPIC',
                '/imu/base_link_corrected',
            ),
            'cmd_vel_topic': os.environ.get(
                'SF_IMU_CORRECTOR_CMD_TOPIC',
                '/cmd_vel_collision_in',
            ),
            'min_calibration_samples': env_int('SF_IMU_CORRECTOR_MIN_SAMPLES', 150),
            'startup_timeout_s': env_float('SF_IMU_CORRECTOR_STARTUP_TIMEOUT_S', 5.0),
            'cmd_timeout_s': env_float('SF_IMU_CORRECTOR_CMD_TIMEOUT_S', 0.75),
            'cmd_linear_threshold': env_float('SF_IMU_CORRECTOR_CMD_LINEAR_THRESHOLD', 0.015),
            'cmd_angular_threshold': env_float('SF_IMU_CORRECTOR_CMD_ANGULAR_THRESHOLD', 0.03),
            'stationary_gyro_threshold': env_float('SF_IMU_CORRECTOR_STATIONARY_GYRO_THRESHOLD', 0.08),
            'zero_clamp_threshold': env_float('SF_IMU_CORRECTOR_ZERO_CLAMP_THRESHOLD', 0.018),
            'bias_alpha': env_float('SF_IMU_CORRECTOR_BIAS_ALPHA', 0.002),
            'bias_limit': env_float('SF_IMU_CORRECTOR_BIAS_LIMIT', 0.15),
            'yaw_rate_variance': env_float('SF_IMU_CORRECTOR_YAW_RATE_VARIANCE', 0.02),
            'publish_uncalibrated': env_bool('SF_IMU_CORRECTOR_PUBLISH_UNCALIBRATED', 'false'),
        }],
    )


def generate_launch_description():
    config_path = os.environ.get('SF_CONFIG', '/app/sensor_fusion.yaml')
    imu_source = resolve_imu_source()
    ekf_node = build_ekf_node()

    if imu_source == 'realsense':
        input_topic = os.environ.get('SF_IMU_INPUT_TOPIC', '/camera/realsense/imu')
        output_topic = os.environ.get('SF_IMU_OUTPUT_TOPIC', '/imu/data')
        nodes = [
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
        ]
        if env_bool('SF_IMU_YAW_CORRECTION_ENABLED', 'true'):
            nodes.append(build_imu_yaw_rate_corrector_node())
        nodes.append(ekf_node)
        return LaunchDescription(nodes)

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
