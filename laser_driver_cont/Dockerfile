FROM ros:humble

# Instalirajte RPLIDAR ROS 2 driver i RMW implementaciju
RUN apt-get update && apt-get install -y \
    ros-humble-rplidar-ros \
    ros-humble-rmw-cyclonedds-cpp \
    && rm -rf /var/lib/apt/lists/*

# Postavite ROS 2 okruženje u bashrc
RUN echo "source /opt/ros/humble/setup.bash" >> /root/.bashrc

# Postavite prilagođeni prompt (samo 'driver_cont:' u plavoj boji)
RUN echo "export PS1='\[\033[1;34m\]driver_cont: \[\033[0m\]'" >> /root/.bashrc

# Postavite ulaznu točku za pokretanje drivera
CMD ["bash", "-c", "source /opt/ros/humble/setup.bash && ros2 launch rplidar_ros rplidar.launch.py"]