from glob import glob

from setuptools import find_packages, setup

package_name = 'x30_fastlio'

setup(
    name=package_name,
    version='0.1.0',
    packages=find_packages(),
    data_files=[
        ('share/ament_index/resource_index/packages', ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name + '/launch', glob('launch/*.py')),
        ('share/' + package_name + '/config', glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='burgerbdd',
    maintainer_email='burgerbdd@gmail.com',
    description='FAST-LIO2 adapter, configuration and launch for the X30 simulator',
    license='Apache-2.0',
    entry_points={
        'console_scripts': [
            'livox_adapter = x30_fastlio.livox_adapter:main',
            'fastlio_localizer = x30_fastlio.localizer:main',
            'grid_mapper = x30_fastlio.grid_mapper:main',
        ],
    },
)
