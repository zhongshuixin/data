"""
sensor_sim_bridge_control 的 setuptools 打包入口.

在 ROS 2 ament_python 包中：
- package.xml：声明依赖与构建类型
- setup.py / setup.cfg：用于安装 Python 包与注册 console_scripts
- data_files：将 launch/config/world 等资源安装到 share/<package_name>，便于 ros2 launch 查找
"""

from glob import glob

from setuptools import find_packages, setup


package_name = "sensor_sim_bridge_control"


setup(
    name=package_name,
    version="0.1.0",
    packages=find_packages(exclude=("test",)),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
        (f"share/{package_name}/launch", glob("launch/*.launch.py")),
        (f"share/{package_name}/config", glob("config/*.yaml")),
        (f"share/{package_name}/worlds", glob("worlds/*.world")),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="teacher",
    maintainer_email="teacher@example.com",
    description="Sensor simulation + ROS2 bridge + minimal closed-loop trigger node (teaching demo)",
    license="Apache-2.0",
    tests_require=["pytest"],
    entry_points={
        "console_scripts": [
            "image_trigger_arm = sensor_sim_bridge_control.image_trigger_arm:main",
        ],
    },
)
