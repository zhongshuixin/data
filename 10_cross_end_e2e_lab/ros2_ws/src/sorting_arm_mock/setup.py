from setuptools import find_packages, setup

package_name = "sorting_arm_mock"

setup(
    name=package_name,
    version="0.0.0",
    packages=find_packages(exclude=("test",)),
    data_files=[
        ("share/ament_index/resource_index/packages", [f"resource/{package_name}"]),
        (f"share/{package_name}", ["package.xml"]),
    ],
    install_requires=["setuptools"],
    zip_safe=True,
    maintainer="teacher",
    maintainer_email="teacher@example.com",
    description="Mock ROS2 node for sorting arm cmd/status and demo telemetry topics (Envelope JSON over std_msgs/String).",
    license="Apache-2.0",
    entry_points={
        "console_scripts": [
            "arm_mock = sorting_arm_mock.arm_mock:main",
        ],
    },
)

