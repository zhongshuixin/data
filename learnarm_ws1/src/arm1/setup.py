#! /usr/bin/python3
from setuptools import setup
from glob import glob
import os

package_name = 'arm1'

setup(
    name=package_name,
    version='0.0.0',
    packages=[package_name],
    data_files=[
        ('share/ament_index/resource_index/packages',
         ['resource/' + package_name]),
        ('share/' + package_name, ['package.xml']),
        # 添加urdf和launch文件夹
        (os.path.join('share', package_name, 'urdf'), glob('urdf/*.*')),
        (os.path.join('share', package_name, 'launch'), glob('launch/*.py')),
        # 在 data_files 列表中添加：
        (os.path.join('share', package_name, 'config'), glob('config/*.yaml')),
    ],
    install_requires=['setuptools'],
    zip_safe=True,
    maintainer='zsx',  # 请替换为您的名字
    maintainer_email='3425265354@qq.com',  # 请替换为您的邮箱
    description='A simple arm robot package for ROS 2 Jazzy',
    license='MIT',  # 与创建时指定的许可证一致
    tests_require=['pytest'],
    entry_points={
        'console_scripts': [
            # 可以在此处添加您的可执行脚本
            'joint_control = arm1.joint_control:main',
            'test_arm_action = arm1.test_arm_action:main',
            'test_arm_publisher = arm1.test_arm_publisher:main',
            'test_arm_hand = arm1.test_arm_hand:main',
        ],
    },
)