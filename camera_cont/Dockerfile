FROM python:3.11-slim

# --- System dependencies ---
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    libjpeg-dev \
    libatlas-base-dev \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

# --- Python dependencies ---
RUN pip install --no-cache-dir \
    rclpy \
    sensor-msgs \
    opencv-python-headless \
    numpy \
    picamera2 \
    opencv-contrib-python-headless

# --- Create app directory ---
WORKDIR /app
COPY camera_node.py .

CMD ["python3", "camera_node.py"]
