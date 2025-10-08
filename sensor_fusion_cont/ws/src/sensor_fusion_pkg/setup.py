from setuptools import setup

package_name = 'sensor_fusion_pkg'

setup(
    name=package_name,
    version='0.1.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages', [f'resource/{package_name}']),
        (f'share/{package_name}', ['package.xml']),
        (f'share/{package_name}/launch', ['launch/sensor_fusion.launch.py']),
        # Install config file placed into config/ by Dockerfile copy step
        (f'share/{package_name}/config', ['config/sensor_fusion.yaml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='Maintainer',
    maintainer_email='example@example.com',
    description='Arduino IMU listener and sensor fusion scaffolding',
    license='MIT',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            'arduino_listener = sensor_fusion_pkg.arduino_listener:main'
        ],
    },
)
