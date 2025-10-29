from launch import LaunchDescription
from launch.actions import ExecuteProcess, SetEnvironmentVariable

def generate_launch_description():
    # Run the Python node directly (no ROS package install needed)
    return LaunchDescription([
        SetEnvironmentVariable(name='PYTHONUNBUFFERED', value='1'),
        ExecuteProcess(
            cmd=['python3', '/app/src/camera_node.py'],
            output='screen'
        ),
    ])
