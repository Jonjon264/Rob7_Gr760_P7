from glob import glob

from setuptools import find_packages, setup

package_name = 'x30_task_executor'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='burgerbdd',
    maintainer_email='burgerbdd@gmail.com',
    description='Runs AI task goals, cancels and teach requests on the simulated X30 via Nav2.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={'console_scripts': ['executor = x30_task_executor.node:main']},
)
