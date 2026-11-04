"""Nav2 for the simulated X30, in two modes.

mode:=mapping     The map is built from the lidar scan at FAST-LIO poses (mapper:=fastlio, default; the map is then in the frame
                  FAST-LIO localizes in) or by SLAM Toolbox (mapper:=slam_toolbox). Nav2 runs on the growing map, so the robot
                  can be driven with the joystick or sent goals while mapping. Save with `ros2 run x30_navigation save_map <world>`.
mode:=navigation  A saved map is served by map_server and the robot localizes with FAST-LIO (default) or AMCL.

Start the simulator first (x30_sim sim.launch.py). This launch starts FAST-LIO itself when it needs it.
"""
import os

from ament_index_python.packages import get_package_share_directory
from launch import LaunchDescription
from launch.actions import DeclareLaunchArgument, IncludeLaunchDescription, OpaqueFunction
from launch.conditions import IfCondition
from launch.launch_description_sources import PythonLaunchDescriptionSource
from launch.substitutions import LaunchConfiguration
from launch_ros.actions import Node


def default_map(world):
    return os.path.join(os.environ.get('X30_ROOT', '/x30'), 'configs', 'maps', world, 'map.yaml')


def launch_setup(context):
    nav = get_package_share_directory('x30_navigation')
    bringup = get_package_share_directory('nav2_bringup')
    mode = LaunchConfiguration('mode').perform(context)
    localization = LaunchConfiguration('localization').perform(context)
    mapper = LaunchConfiguration('mapper').perform(context)
    use_sim_time = LaunchConfiguration('use_sim_time').perform(context)
    params = LaunchConfiguration('params_file').perform(context)
    map_yaml = LaunchConfiguration('map').perform(context) or default_map(LaunchConfiguration('world').perform(context))
    sim_time = {'use_sim_time': use_sim_time.lower() == 'true'}
    include = lambda path, args: IncludeLaunchDescription(PythonLaunchDescriptionSource(path), launch_arguments=args.items())

    actions = [Node(
        package='pointcloud_to_laserscan', executable='pointcloud_to_laserscan_node', name='pointcloud_to_laserscan',
        remappings=[('cloud_in', '/lidar_points'), ('scan', '/scan')],
        parameters=[os.path.join(nav, 'config', 'scan.yaml'), sim_time], output='screen')]

    fastlio = include(os.path.join(get_package_share_directory('x30_fastlio'), 'launch', 'fastlio.launch.py'), {
        'use_sim_time': use_sim_time, 'localizer': 'true'})
    if mode == 'mapping' and mapper == 'fastlio':
        actions += [fastlio, Node(package='x30_fastlio', executable='grid_mapper', name='grid_mapper', output='screen',
                                  parameters=[{'range_min': 0.6}, sim_time])]
    elif mode == 'mapping':
        actions.append(include(os.path.join(get_package_share_directory('slam_toolbox'), 'launch', 'online_async_launch.py'), {
            'slam_params_file': os.path.join(nav, 'config', 'slam_toolbox_params.yaml'), 'use_sim_time': use_sim_time}))
    else:
        if not os.path.isfile(map_yaml):
            raise RuntimeError(f'Map not found: {map_yaml}. Map the world first (mode:=mapping) or pass map:=...')
        if localization == 'amcl':
            actions.append(include(os.path.join(bringup, 'launch', 'localization_launch.py'), {
                'map': map_yaml, 'params_file': params, 'use_sim_time': use_sim_time, 'autostart': 'true'}))
        else:
            actions += [
                Node(package='nav2_map_server', executable='map_server', name='map_server', output='screen',
                     parameters=[{'yaml_filename': map_yaml}, sim_time]),
                Node(package='nav2_lifecycle_manager', executable='lifecycle_manager', name='lifecycle_manager_localization',
                     output='screen', parameters=[{'autostart': True, 'node_names': ['map_server']}, sim_time]),
                fastlio,
            ]
    actions.append(include(os.path.join(bringup, 'launch', 'navigation_launch.py'), {
        'params_file': params, 'use_sim_time': use_sim_time, 'autostart': 'true'}))
    actions.append(Node(package='rviz2', executable='rviz2', arguments=['-d', os.path.join(nav, 'rviz', 'nav2.rviz')],
                        parameters=[sim_time], condition=IfCondition(LaunchConfiguration('rviz'))))
    return actions


def generate_launch_description():
    nav = get_package_share_directory('x30_navigation')
    return LaunchDescription([
        DeclareLaunchArgument('mode', default_value='navigation', description='mapping | navigation'),
        DeclareLaunchArgument('mapper', default_value='fastlio', description='mapping mode: fastlio | slam_toolbox'),
        DeclareLaunchArgument('localization', default_value='fastlio', description='navigation mode: fastlio | amcl'),
        DeclareLaunchArgument('world', default_value='aws_hospital', description='selects configs/maps/<world>/map.yaml'),
        DeclareLaunchArgument('map', default_value='', description='map yaml; overrides the world default'),
        DeclareLaunchArgument('use_sim_time', default_value='true'),
        DeclareLaunchArgument('params_file', default_value=os.path.join(nav, 'config', 'nav2_params.yaml')),
        DeclareLaunchArgument('rviz', default_value='false'),
        OpaqueFunction(function=launch_setup),
    ])
