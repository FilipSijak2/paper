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
    libopencv-dev \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

# --------- ROS2 environment (mounted from host in docker-compose) ---------
ENV ROS2_INSTALL=/opt/ros/humble
ENV PATH=$ROS2_INSTALL/bin:$PATH
ENV LD_LIBRARY_PATH=$ROS2_INSTALL/lib:$LD_LIBRARY_PATH
ENV PYTHONPATH=$ROS2_INSTALL/lib/python3.11/site-packages:$PYTHONPATH
ENV ROS_DOMAIN_ID=0
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp

# --------- Workdir ---------
WORKDIR /app

# --------- Copy only the Python ROS2 node ---------
COPY camera_node.py /app/camera_node.py

# --------- Python dependencies ---------
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    rclpy \
    sensor-msgs \
    cv-bridge \
    numpy

# --------- Entrypoint ---------
ENTRYPOINT ["python3", "/app/camera_node.py"]