cmake_minimum_required(VERSION 3.22)
project(robot_arm_config)

find_package(ament_cmake REQUIRED)

ament_package()

# 安装 launch：排除 setup_assistant.launch，避免打包交互向导的专用入口
if(EXISTS "${CMAKE_CURRENT_SOURCE_DIR}/launch")
  install(
    DIRECTORY launch
    DESTINATION share/${PROJECT_NAME}
    PATTERN "setup_assistant.launch" EXCLUDE)
endif()

# 安装 MoveIt 配置文件与 Setup Assistant 元数据
install(DIRECTORY config DESTINATION share/${PROJECT_NAME})
install(FILES .setup_assistant DESTINATION share/${PROJECT_NAME})
