#!/bin/bash

# 设置颜色输出
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# 打印带颜色的消息
print_message() {
    echo -e "${2}${1}${NC}"
}

# 检查Python环境
check_python() {
    print_message "检查Python环境..." "$YELLOW"
    if ! command -v python3 &> /dev/null; then
        print_message "错误: 未找到Python3" "$RED"
        exit 1
    fi
    print_message "Python环境检查通过" "$GREEN"
}

# 检查依赖安装
check_dependencies() {
    print_message "检查依赖安装..." "$YELLOW"
    if ! pip show playwright &> /dev/null; then
        print_message "安装Playwright..." "$YELLOW"
        pip install -r requirements-mcp.txt
        python -m playwright install
    fi
    print_message "依赖检查通过" "$GREEN"
}

# 运行简单测试
run_simple_test() {
    print_message "运行简单测试..." "$YELLOW"
    python test-simple.py
    if [ $? -eq 0 ]; then
        print_message "简单测试完成" "$GREEN"
    else
        print_message "简单测试失败" "$RED"
    fi
}

# 运行Playwright测试
run_playwright_test() {
    print_message "运行Playwright测试..." "$YELLOW"
    python test-playwright.py
    if [ $? -eq 0 ]; then
        print_message "Playwright测试完成" "$GREEN"
    else
        print_message "Playwright测试失败" "$RED"
    fi
}

# 运行MCP实现测试
run_mcp_test() {
    print_message "运行MCP实现测试..." "$YELLOW"
    python mcp_implementation.py
    if [ $? -eq 0 ]; then
        print_message "MCP实现测试完成" "$GREEN"
    else
        print_message "MCP实现测试失败" "$RED"
    fi
}

# 主函数
main() {
    print_message "开始数字孪生测试..." "$YELLOW"
    
    # 检查环境
    check_python
    check_dependencies
    
    # 运行测试
    run_simple_test
    run_playwright_test
    run_mcp_test
    
    print_message "测试完成" "$GREEN"
}

# 执行主函数
main 