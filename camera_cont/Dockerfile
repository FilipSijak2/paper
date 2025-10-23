FROM ubuntu:24.03

# Install dependencies
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libcamera-apps \
    python3 \
    python3-pip \
    && rm -rf /var/lib/apt/lists/*

# Optional: install ROS 2 Python packages if needed
RUN pip3 install rclpy sensor-msgs

# Set working directory
WORKDIR /app

# Copy your camera ROS node (Python)
COPY camera_node.py .

CMD ["python3", "camera_node.py"]
