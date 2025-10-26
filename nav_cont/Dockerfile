FROM ros:humble

# Install dependencies
RUN apt-get update && apt-get install -y \
    git \
    build-essential \
    cmake \
    python3-colcon-common-extensions \
    python3-opencv \
    ros-humble-cv-bridge \
    ros-humble-image-transport \
    ros-humble-camera-info-manager \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Create workspace
WORKDIR /ros2_ws/src

# Clone Rolling libcamera ROS driver
RUN git clone https://github.com/raspberrypi/libcamera_ros.git -b rolling

# Go to workspace and build
WORKDIR /ros2_ws
RUN . /opt/ros/humble/setup.sh && colcon build --merge-install

# Auto source environment
RUN echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc

# ROS middleware
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Set default launch (with resolution parameter)
CMD ["bash", "-c", "source /ros2_ws/install/setup.bash && ros2 launch libcamera_ros libcamera.launch.py camera_info_url:=file:///camera_info.yaml --ros-args -p image_width:=1280 -p image_height:=720 -p framerate:=30"]
