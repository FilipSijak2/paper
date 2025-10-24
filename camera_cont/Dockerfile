# --- Base image ---
FROM ubuntu:24.04

# --- Set noninteractive frontend ---
ENV DEBIAN_FRONTEND=noninteractive

# --- Install system dependencies ---
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    python3-opencv \
    v4l-utils \
    libcamera-apps \
    && rm -rf /var/lib/apt/lists/*

# --- Install ROS 2 Python dependencies ---
RUN python3 -m pip install --no-cache-dir --break-system-packages \
    opencv-python \
    numpy \
    rclpy \
    sensor-msgs \
    cv-bridge

# --- Set working directory ---
WORKDIR /app

# --- Copy camera publisher script ---
COPY camera_publisher.py /app/

# --- Default command ---
CMD ["python3", "/app/camera_publisher.py"]

