# ------------------------------------------------------------
# Base: ROS 2 Humble (Ubuntu 22.04 userland u containeru)
# Host OS ostaje Ubuntu 24.04
# ------------------------------------------------------------
FROM ros:humble-ros-base

# Brži apt & osnovni alati
ENV DEBIAN_FRONTEND=noninteractive
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget curl ca-certificates gnupg2 lsb-release \
    build-essential cmake pkg-config git \
    python3-pip python3-colcon-common-extensions \
    # libcamera i ovisnosti
    libcamera-dev libjpeg-dev libtiff-dev libpng-dev \
    libdrm-dev libexif-dev libboost-all-dev libopencv-dev \
    # ROS image transport (za Foxglove)
    ros-humble-image-transport ros-humble-image-transport-plugins \
 && rm -rf /var/lib/apt/lists/*

# RMW + legacy libcamera pipeline (zaobiđi PiSP/DMA)
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV LIBCAMERA_RPI_USE_LEGACY=1
# (ostavi vidljivo ako dodaš lokalni build libcamera/rpicam-apps)
ENV LD_LIBRARY_PATH=/usr/local/lib/aarch64-linux-gnu:$LD_LIBRARY_PATH
ENV PKG_CONFIG_PATH=/usr/local/lib/aarch64-linux-gnu/pkgconfig:$PKG_CONFIG_PATH

# ------------------------------------------------------------
# ROS2 workspace
# ------------------------------------------------------------
WORKDIR /ros2_ws/src

# Preuzmi libcamera_ros (snapshot bez git-a)
# Preuzmi libcamera_ros (Humble branch)
RUN wget https://github.com/raspberrypi/libcamera_ros/archive/refs/heads/humble.tar.gz -O libcamera_ros.tar.gz \
 && tar -xzf libcamera_ros.tar.gz \
 && rm libcamera_ros.tar.gz \
 && mv libcamera_ros-humble libcamera_ros

# (Opcionalno: pin na commit)
# RUN wget https://github.com/raspberrypi/libcamera_ros/archive/<COMMIT>.tar.gz -O libcamera_ros.tar.gz && ...

WORKDIR /ros2_ws

# Build overlay
RUN bash -lc "source /opt/ros/$ROS_DISTRO/setup.bash && colcon build --symlink-install"

# Autoload overlay na startu
RUN echo 'source /opt/ros/$ROS_DISTRO/setup.bash' >> /root/.bashrc \
 && echo 'source /ros2_ws/install/setup.bash' >> /root/.bashrc

# Default
CMD ["bash"]


