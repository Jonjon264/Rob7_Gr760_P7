from setuptools import find_packages, setup

package_name = 'robot_task_handler'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ROB7',
    maintainer_email='maintainer@example.com',
    description='Dispatch manager JSON to ROS 2 goal and cancellation topics.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={
        'console_scripts': ['handler = robot_task_handler.node:main'],
    },
)
