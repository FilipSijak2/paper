FROM ros:humble

# Install required dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    cmake \
    python3-colcon-common-extensions \
    python3-opencv \
    libcamera-apps \
    ros-humble-ros-base \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    && rm -rf /var/lib/apt/lists/*

# Create workspace
WORKDIR /ros2_ws/src

# Clone Rolling libcamera ROS driver
RUN git clone https://github.com/raspberrypi/libcamera_ros.git -b rolling

# Go back to workspace root
WORKDIR /ros2_ws

# Build Rolling libcamera_ros with Humble
RUN . /opt/ros/humble/setup.sh && colcon build --merge-install

# Auto-source workspace
RUN echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc

ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

CMD ["bash", "-c", "source /ros2_ws/install/setup.bash && ros2 launch libcamera_ros libcamera.launch.py camera_info_url:=file:///camera_info.yaml"]
