FROM ubuntu:24.04

# --- System dependencies ---
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-pip \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

# --- Python dependencies ---
RUN python3 -m pip install --no-cache-dir \
    opencv-python \
    numpy \
    rclpy \
    sensor-msgs \
    cv-bridge

WORKDIR /app
COPY camera_publisher.py /app/

CMD ["python3", "/app/camera_publisher.py"]

