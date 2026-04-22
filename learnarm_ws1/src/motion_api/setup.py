"""motion_api 包的安装脚本

- 安装共享资源（launch/config）供 ros2 查找
- 注册 console_scripts，以便通过 `ros2 run motion_api ...` 启动示例
"""
from setuptools import find_packages, setup
from glob import glob

package_name = 'motion_api'

setup(
    name=package_name,
    version='0.0.0',
    packages=find_packages(exclude=['test']),
    data_files=[
        ('share/ament_index/resource_index/packages',
            ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        ('share/' + package_name+'/launch', glob("launch/*.launch.py")),
        ('share/' + package_name+'/config', glob("config/*")),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='mccharley',
    maintainer_email='brucelin92@163.com',
    description='TODO: Package description',
    license='MIT',
    extras_require={
        'test': [
            'pytest',
        ],
    },
    entry_points={
        'console_scripts': [
            'motion_api_test = motion_api.motion_planning_python_api:main',
            'pick_drop = motion_api.pick_drop:main',
            'pick_rose_drop = motion_api.pick_rose_drop:main',
        ],
    },
)
