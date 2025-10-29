FROM ros:humble-ros-base

# Instaliraj osnovne pakete i libcamera ovisnosti
RUN apt-get update && apt-get install -y \
    git \
    python3-pip \
    python3-colcon-common-extensions \
    build-essential \
    libcamera-dev \
    libcamera-apps \
    cmake \
    && rm -rf /var/lib/apt/lists/*

# Postavi radni prostor
WORKDIR /ros2_ws
RUN mkdir -p src

# ✅ U ovom trenutku GitHub Actions workflow treba napraviti:
# actions/checkout@v4 za tvoj repo
# i actions/checkout za libcamera_ros u libcamera_ros/

# Kopiraj lokalno kloniran libcamera_ros u src
COPY libcamera_ros src/libcamera_ros

# Source ROS environment
RUN /bin/bash -c "source /opt/ros/humble/setup.bash && colcon build --symlink-install"

# Source pri pokretanju containera
CMD ["/bin/bash", "-c", "source /ros2_ws/install/setup.bash && ros2 run libcamera_ros libcamera_ros_node"]
