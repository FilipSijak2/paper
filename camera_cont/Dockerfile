FROM ubuntu:24.04

# --- System dependencies ---
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-pip \
    python3-opencv \
    v4l-utils \
    libcamera-dev \
    && rm -rf /var/lib/apt/lists/*

# --- Install ROS Python dependencies ---
RUN python3 -m pip install --no-cache-dir rclpy sensor-msgs cv-bridge numpy

WORKDIR /app
COPY camera_publisher.py /app/

# Set ROS environment variables from parent container
ENV RMW_IMPLEMENTATION=rmw_cyclonedds_cpp
ENV ROS_DOMAIN_ID=0

CMD ["python3", "/app/camera_publisher.py"]
