# =========================================================
# 1. BASE IMAGE (ROS Humble with tools)
# =========================================================
FROM ros:humble-ros-base

# =========================================================
# 2. Install dependencies
# =========================================================
RUN apt-get update && apt-get install -y \
    git cmake python3-colcon-common-extensions \
    libcamera-dev libcamera-apps libjpeg-dev libpng-dev libtiff-dev \
    libavcodec-dev libavformat-dev libswscale-dev \
    && rm -rf /var/lib/apt/lists/*

# =========================================================
# 3. Create workspace
# =========================================================
WORKDIR /ros2_ws
RUN mkdir -p src

# =========================================================
# 4. Clone libcamera_ros (specific branch for ROS2 + IMX708)
# =========================================================
RUN git clone --depth 1 --branch humble https://github.com/raspberrypi/libcamera_ros.git src/libcamera_ros || \
    git clone --depth 1 https://github.com/raspberrypi/libcamera_ros.git src/libcamera_ros

# =========================================================
# 5. Build
# =========================================================
RUN . /opt/ros/humble/setup.sh && \
    colcon build --symlink-install

# =========================================================
# 6. Setup runtime environment
# =========================================================
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc
RUN echo "source /ros2_ws/install/setup.bash" >> /root/.bashrc

# =========================================================
# 7. Default command
# =========================================================
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && \
                   source /ros2_ws/install/setup.bash && \
                   ros2 run libcamera_ros libcamera_ros_node"]
