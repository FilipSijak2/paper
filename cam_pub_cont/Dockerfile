# ===== Dockerfile =====
FROM ros:humble-ros-base

# Osnovne alatke i libcamera ovisnosti
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential cmake git pkg-config \
    python3-colcon-common-extensions python3-vcstool \
    libcamera-dev libevent-dev libdrm-dev libjpeg-dev libtiff5-dev \
    libavcodec-dev libavformat-dev libavutil-dev libswscale-dev \
    libepoxy-dev libyaml-cpp-dev \
    && rm -rf /var/lib/apt/lists/*

# Radni prostor
ENV ROS_WS=/opt/ros_ws
RUN mkdir -p $ROS_WS/src
WORKDIR $ROS_WS

# (1) Libcamera ROS node (izvor) – provjereni community node
# Ako već imaš svoj repo, ovdje promijeni URL i folder naziv
RUN git clone https://github.com/raspberrypi/libcamera_ros.git src/libcamera_ros

# Build
RUN . /opt/ros/humble/setup.sh && colcon build --packages-select libcamera_ros

# Runtime env
ENV ROS_DOMAIN_ID=0
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# Učitavanje ROS env-a pri startu
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Libcamera treba pristup uređajima
# (vidjet ćeš ih kroz docker-compose "devices")
ENTRYPOINT ["/entrypoint.sh"]
CMD ["bash"]
