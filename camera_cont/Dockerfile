FROM ros:humble

# Install required dependencies
RUN apt-get update && apt-get install -y \
    python3-colcon-common-extensions \
    python3-pip \
    libopencv-dev python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Create workspace
WORKDIR /ros_ws
RUN mkdir -p src

# Copy source code (Python node & launch file)
COPY src/ src/
COPY launch/ launch/

# Build (catkin not needed, pure Python)
RUN . /opt/ros/humble/setup.sh && colcon build --symlink-install

# Environment setup
ENV ROS_DOMAIN_ID=0
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Source ROS2 and run your launch file
CMD ["/bin/bash", "-c", "source /opt/ros/humble/setup.sh && source install/setup.sh && ros2 launch camera_stream camera.launch.py"]





