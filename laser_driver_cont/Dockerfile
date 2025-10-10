FROM ros:humble

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    python3-colcon-common-extensions \
    build-essential \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Set variables for ROS 2
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Create workspace
WORKDIR /ros2_ws
RUN mkdir src

# Clone rplidar_ros from ros2 branch
RUN git clone -b ros2 https://github.com/Slamtec/rplidar_ros.git src/rplidar_ros

# Build workspace
RUN . /opt/ros/humble/setup.sh && colcon build

# Set environment and prompt
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc && \
    echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc && \
    echo "export PS1='\[\033[1;34m\]driver_cont: \[\033[0m\]'" >> /root/.bashrc

# Start driver (or bash if it fails)
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && source /ros2_ws/install/setup.bash && ros2 launch rplidar_ros rplidar_a1_launch.py && view_rplidar_a1_launch.py || bash"]