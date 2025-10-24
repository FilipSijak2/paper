FROM ubuntu:24.04

# --- System dependencies ---
RUN apt-get update && DEBIAN_FRONTEND=noninteractive apt-get install -y \
    python3 \
    python3-pip \
    python3-opencv \
    libcamera-apps \
    v4l-utils \
    && rm -rf /var/lib/apt/lists/*

# --- Python dependencies ---
RUN python3 -m pip install --no-cache-dir numpy

WORKDIR /app
COPY camera_publisher.py /app/

CMD ["python3", "/app/camera_publisher.py"]
