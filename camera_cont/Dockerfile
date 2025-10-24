# --------- Base Image ---------
FROM ubuntu:24.04

# --------- Environment ---------
ENV DEBIAN_FRONTEND=noninteractive
ENV LANG=C.UTF-8
ENV LC_ALL=C.UTF-8
ENV ROS_DISTRO=humble

# --------- Install dependencies ---------
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-opencv \
    python3-yaml \
    python3-rosdep \
    libopencv-dev \
    libboost-dev \
    libgnutls28-dev \
    libtiff-dev \
    pybind11-dev \
    cmake \
    meson \
    ninja-build \
    v4l-utils \
    libcamera-apps \
    && rm -rf /var/lib/apt/lists/*

# --------- ROS 2 Humble setup ---------
# Mount host ROS2 at runtime (avoids building ROS2 in container)
ENV ROS2_INSTALL=/opt/ros/humble
ENV PATH=$ROS2_INSTALL/bin:$PATH
ENV LD_LIBRARY_PATH=$ROS2_INSTALL/lib
ENV PYTHONPATH=$ROS2_INSTALL/lib/python3.11/site-packages
ENV ROS_DOMAIN_ID=0
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# --------- Workdir ---------
WORKDIR /app

# --------- Copy camera ROS2 node ---------
# Pretpostavimo da imaš node u ./src/camera_node/
COPY ./src/camera_node /app/camera_node
COPY camera_node.py /app/camera_node.py

# Install Python dependencies for ROS2 node
RUN pip3 install --no-cache-dir \
    rclpy \
    sensor-msgs \
    cv-bridge \
    numpy

# --------- Entrypoint ---------
# Node starta RAW feed s CSI kamere
ENTRYPOINT ["python3", "/app/camera_node.py"]

