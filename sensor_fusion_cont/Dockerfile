FROM ros:humble

# OS dependencies + ROS 2 paketi
RUN apt-get update && apt-get install -y \
    python3-pip \
    ros-humble-robot-localization \
    ros-humble-serial \
    ros-humble-imu-tools \
    ros-humble-tf2-ros \
    ros-humble-geometry-msgs \
    ros-humble-nav-msgs \
    && rm -rf /var/lib/apt/lists/*

# Python dependencies
RUN pip3 install pyserial numpy

# Postavi ROS okruženje
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc
RUN echo "export PS1='\[\033[1;34m\]sensor_fusion: \[\033[0m\]'" >> /root/.bashrc

WORKDIR /app
COPY sensor_fusion.yaml /app/sensor_fusion.yaml
COPY arduino_listener.py /app/arduino_listener.py

CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && python3 /app/arduino_listener.py"]
