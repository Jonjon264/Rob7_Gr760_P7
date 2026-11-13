from glob import glob

from setuptools import find_packages, setup

package_name = 'qwen_voice_manager'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml', 'requirements-voice.txt']),
        ('share/' + package_name + '/launch', glob('launch/*.launch.py')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='ROB7',
    maintainer_email='maintainer@example.com',
    description='Voice interface: speech to Qwen to robot commands, with spoken replies.',
    license='Apache-2.0',
    tests_require=['pytest'],
    entry_points={'console_scripts': [
        'voice_manager = qwen_voice_manager.node:main',
        'ask_qwen = qwen_voice_manager.cli:main',
    ]},
)
