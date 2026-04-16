from setuptools import find_packages, setup

package_name = "sorting_arm_control"

setup(
    name=package_name,
    version="0.0.1",
    packages=find_packages(exclude=["test"]),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="teacher",
    maintainer_email="teacher@example.com",
    description="ROS2 side device control node for sorting arm command execution and status feedback.",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "sorting_arm_control_node = sorting_arm_control.control_node:main",
        ],
    },
)
