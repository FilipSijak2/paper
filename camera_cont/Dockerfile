FROM ubuntu:24.04

# Install dependencies
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libcamera-apps \
    python3 \
    python3-pip \
    python3-opencv \
    && rm -rf /var/lib/apt/lists/*

# Install ROS 2 Python packages
RUN pip3 install rclpy sensor-msgs cv_bridge

# Set working directory
WORKDIR /app
COPY camera_node.py .

CMD ["python3", "camera_node.py"]
