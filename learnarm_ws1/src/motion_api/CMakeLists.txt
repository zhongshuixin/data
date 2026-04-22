cmake_minimum_required(VERSION 3.8)
project(motion_api)

if(NOT CMAKE_CXX_STANDARD)
  set(CMAKE_CXX_STANDARD 17)
endif()

if(CMAKE_PROJECT_NAME STREQUAL PROJECT_NAME)
  find_package(ament_cmake REQUIRED)
  find_package(ament_cmake_pytest REQUIRED)
  find_package(rclpy REQUIRED)
endif()

find_package(Python3 REQUIRED COMPONENTS Interpreter Development)

ament_python_install_package(${PROJECT_NAME})

install(
  FILES
    config/pink_cylinder.sdf
    config/blue.urdf
    config/red.urdf
    config/green.urdf
  DESTINATION share/${PROJECT_NAME}/config
)

install(
  FILES
    launch/load_all_models.launch.py
  DESTINATION share/${PROJECT_NAME}/launch
)

if(BUILD_TESTING)
  find_package(ament_cmake REQUIRED)
  ament_add_pytest_test(test_motion_api test/test_motion_api.py
    TIMEOUT 30
  )
endif()

ament_package()