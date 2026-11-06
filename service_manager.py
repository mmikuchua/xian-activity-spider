#!/usr/bin/env python3
"""
西安本地宝活动爬虫API服务管理器
用于启动API服务、ngrok隧道和监控状态
"""

import subprocess
import sys
import time
import os
import threading
import signal
import webbrowser
import requests
import json
from datetime import datetime
import atexit


class ServiceManager:
    def __init__(self):
        self.api_process = None
        self.ngrok_process = None
        self.api_port = 5000
        self.ngrok_url = None
        self.running = False

        # 颜色代码（用于终端美化）
        self.COLORS = {
            'red': '\033[91m',
            'green': '\033[92m',
            'yellow': '\033[93m',
            'blue': '\033[94m',
            'magenta': '\033[95m',
            'cyan': '\033[96m',
            'white': '\033[97m',
            'reset': '\033[0m',
            'bold': '\033[1m'
        }

    def color_print(self, text, color='white', bold=False):
        """彩色打印"""
        color_code = self.COLORS.get(color, self.COLORS['white'])
        bold_code = self.COLORS['bold'] if bold else ''
        reset_code = self.COLORS['reset']
        print(f"{bold_code}{color_code}{text}{reset_code}")

    def print_header(self):
        """打印头部信息"""
        print("\n" + "=" * 70)
        self.color_print("🚀 西安本地宝活动爬虫API - 服务管理器", "cyan", True)
        self.color_print("=" * 70, "cyan")

    def print_menu(self):
        """打印菜单"""
        print("\n" + "=" * 70)
        self.color_print("📋 主菜单", "yellow", True)
        print("=" * 70)
        self.color_print("1. 启动API服务", "green")
        self.color_print("2. 启动ngrok隧道", "green")
        self.color_print("3. 同时启动API和ngrok", "green")
        self.color_print("4. 测试API连接", "blue")
        self.color_print("5. 查看当前状态", "blue")
        self.color_print("6. 停止所有服务", "red")
        self.color_print("7. 打开本地测试页面", "magenta")
        self.color_print("8. Coze插件配置指南", "cyan")
        self.color_print("9. 退出", "red")
        print("=" * 70)

    def check_api_running(self):
        """检查API是否在运行"""
        try:
            response = requests.get(f"http://localhost:{self.api_port}/api/health", timeout=2)
            return response.status_code == 200
        except:
            return False

    def start_api_service(self, show_output=True):
        """启动API服务"""
        if self.check_api_running():
            self.color_print("✅ API服务已经在运行", "green")
            return True

        self.color_print("🚀 正在启动API服务...", "yellow")

        # 确保在正确的目录
        script_dir = os.path.dirname(os.path.abspath(__file__))
        os.chdir(script_dir)

        try:
            # 启动API进程
            self.api_process = subprocess.Popen(
                [sys.executable, "activity_api.py"],
                stdout=subprocess.PIPE if not show_output else sys.stdout,
                stderr=subprocess.PIPE if not show_output else sys.stderr,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # 等待启动
            self.color_print("⏳ 等待API服务启动...", "yellow")

            for i in range(15):  # 最多等待30秒
                if self.check_api_running():
                    self.color_print(f"✅ API服务启动成功！运行在: http://localhost:{self.api_port}", "green")
                    self.running = True

                    # 启动一个线程来监控API进程
                    if not show_output:
                        threading.Thread(target=self.monitor_api_output, daemon=True).start()

                    return True

                # 检查进程是否已经退出
                if self.api_process.poll() is not None:
                    stdout, stderr = self.api_process.communicate()
                    self.color_print(f"❌ API进程异常退出: {stderr}", "red")
                    return False

                time.sleep(2)

            self.color_print("❌ API服务启动超时", "red")
            return False

        except Exception as e:
            self.color_print(f"❌ 启动API服务失败: {e}", "red")
            return False

    def monitor_api_output(self):
        """监控API输出（在后台线程中运行）"""
        try:
            while True:
                if self.api_process:
                    output = self.api_process.stdout.readline()
                    if output:
                        print(f"[API] {output.strip()}")
                    else:
                        break
        except:
            pass

    def start_ngrok_tunnel(self):
        """启动ngrok隧道"""
        self.color_print("🌐 正在启动ngrok隧道...", "yellow")

        try:
            # 检查ngrok是否可用
            result = subprocess.run(['ngrok', '--version'],
                                    capture_output=True, text=True)
            if result.returncode != 0:
                self.color_print("❌ ngrok未找到或未配置", "red")
                self.color_print("请确保:", "yellow")
                self.color_print("1. 已从 https://ngrok.com/download 下载ngrok", "yellow")
                self.color_print("2. 已解压到可访问的目录", "yellow")
                self.color_print("3. 已配置authtoken: ngrok config add-authtoken YOUR_TOKEN", "yellow")
                self.color_print("4. 已将ngrok所在目录添加到PATH环境变量", "yellow")
                return None

            # 启动ngrok
            self.color_print("启动ngrok隧道连接到端口 5000...", "yellow")

            # 使用subprocess启动ngrok，捕获输出
            self.ngrok_process = subprocess.Popen(
                ['ngrok', 'http', '127.0.0.1:5000'],
                stdout=subprocess.PIPE,
                stderr=subprocess.STDOUT,
                text=True,
                bufsize=1,
                universal_newlines=True
            )

            # 等待并尝试获取ngrok URL
            time.sleep(3)

            # 尝试从ngrok的API获取隧道信息
            try:
                response = requests.get("http://localhost:4040/api/tunnels", timeout=5)
                if response.status_code == 200:
                    data = response.json()
                    tunnels = data.get('tunnels', [])
                    if tunnels:
                        self.ngrok_url = tunnels[0].get('public_url')
                        self.color_print(f"✅ ngrok隧道启动成功！", "green")
                        self.color_print(f"🌍 公网URL: {self.ngrok_url}", "cyan", True)

                        # 启动线程监控ngrok输出
                        threading.Thread(target=self.monitor_ngrok_output, daemon=True).start()

                        return self.ngrok_url
            except:
                # 如果无法从API获取，尝试从进程输出中解析
                self.color_print("⚠️  正在等待ngrok输出URL...", "yellow")

                # 给更多时间启动
                time.sleep(2)

                # 尝试从输出中读取
                try:
                    if self.ngrok_process.stdout:
                        for _ in range(5):
                            line = self.ngrok_process.stdout.readline()
                            if line and 'Forwarding' in line:
                                parts = line.strip().split('->')
                                if len(parts) > 0:
                                    self.ngrok_url = parts[0].replace('Forwarding', '').strip()
                                    self.color_print(f"✅ ngrok隧道启动成功！", "green")
                                    self.color_print(f"🌍 公网URL: {self.ngrok_url}", "cyan", True)
                                    return self.ngrok_url
                            time.sleep(1)
                except:
                    pass

            self.color_print("⚠️  ngrok已启动，但无法获取URL", "yellow")
            self.color_print("请手动查看ngrok窗口中的'Forwarding' URL", "yellow")
            return None

        except Exception as e:
            self.color_print(f"❌ 启动ngrok失败: {e}", "red")
            return None

    def monitor_ngrok_output(self):
        """监控ngrok输出（在后台线程中运行）"""
        try:
            while True:
                if self.ngrok_process and self.ngrok_process.stdout:
                    output = self.ngrok_process.stdout.readline()
                    if output:
                        print(f"[ngrok] {output.strip()}")
                    else:
                        break
        except:
            pass

    def test_connections(self):
        """测试所有连接"""
        self.color_print("\n🔍 正在测试连接...", "yellow")

        # 测试本地API
        self.color_print("1. 测试本地API连接:", "blue")
        try:
            response = requests.get(f"http://localhost:{self.api_port}/api/health", timeout=5)
            if response.status_code == 200:
                self.color_print(f"   ✅ 本地API正常: http://localhost:{self.api_port}", "green")
                data = response.json()
                print(f"      状态: {data.get('status', 'N/A')}")
                print(f"      时间: {data.get('timestamp', 'N/A')}")
            else:
                self.color_print(f"   ❌ 本地API异常: 状态码 {response.status_code}", "red")
        except Exception as e:
            self.color_print(f"   ❌ 本地API连接失败: {e}", "red")

        # 测试ngrok（如果有）
        if self.ngrok_url:
            self.color_print(f"\n2. 测试公网连接 ({self.ngrok_url}):", "blue")
            try:
                response = requests.get(f"{self.ngrok_url}/api/health", timeout=10)
                if response.status_code == 200:
                    self.color_print(f"   ✅ 公网连接正常", "green")
                    data = response.json()
                    print(f"      状态: {data.get('status', 'N/A')}")
                else:
                    self.color_print(f"   ❌ 公网连接异常: 状态码 {response.status_code}", "red")
            except Exception as e:
                self.color_print(f"   ❌ 公网连接失败: {e}", "red")

        # 测试获取活动数据
        self.color_print("\n3. 测试获取活动数据:", "blue")
        try:
            response = requests.get(f"http://localhost:{self.api_port}/api/activities?limit=2", timeout=10)
            if response.status_code == 200:
                data = response.json()
                count = len(data.get('data', []))
                self.color_print(f"   ✅ 获取活动数据成功，获取 {count} 条记录", "green")
                if count > 0:
                    first_activity = data['data'][0]
                    print(f"      示例: {first_activity.get('title', 'N/A')[:50]}...")
            else:
                self.color_print(f"   ❌ 获取活动数据失败: 状态码 {response.status_code}", "red")
        except Exception as e:
            self.color_print(f"   ❌ 获取活动数据失败: {e}", "red")

    def show_status(self):
        """显示当前状态"""
        self.color_print("\n📊 当前服务状态", "cyan", True)
        print("-" * 50)

        # API状态
        api_status = "✅ 运行中" if self.check_api_running() else "❌ 已停止"
        self.color_print(f"API服务: {api_status}", "green" if self.check_api_running() else "red")
        if self.check_api_running():
            print(f"   本地地址: http://localhost:{self.api_port}")
            print(f"   测试地址: http://localhost:{self.api_port}/api/health")

        # ngrok状态
        ngrok_status = "✅ 运行中" if self.ngrok_process and self.ngrok_process.poll() is None else "❌ 已停止"
        self.color_print(f"ngrok隧道: {ngrok_status}", "green" if ngrok_status == "✅ 运行中" else "red")
        if self.ngrok_url:
            print(f"   公网URL: {self.ngrok_url}")
            print(f"   测试地址: {self.ngrok_url}/api/health")

        # 文件保存状态
        print("\n💾 文件保存:")
        try:
            files = os.listdir('.')
            csv_files = [f for f in files if f.endswith('.csv') and '西安本地宝活动' in f]
            if csv_files:
                csv_files.sort(reverse=True)
                print(f"   最新CSV文件: {csv_files[0]}")
                print(f"   CSV文件总数: {len(csv_files)}")
            else:
                print("   暂无CSV文件")
        except:
            print("   无法检查文件")

        print("-" * 50)

    def stop_all_services(self):
        """停止所有服务"""
        self.color_print("\n⏹️  正在停止所有服务...", "yellow")

        stopped = False

        # 停止ngrok
        if self.ngrok_process and self.ngrok_process.poll() is None:
            self.color_print("停止ngrok隧道...", "yellow")
            try:
                if os.name == 'nt':  # Windows
                    subprocess.run(['taskkill', '/F', '/T', '/PID', str(self.ngrok_process.pid)],
                                   capture_output=True)
                else:  # Linux/Mac
                    self.ngrok_process.terminate()
                    self.ngrok_process.wait(timeout=5)
                self.color_print("✅ ngrok已停止", "green")
                stopped = True
            except:
                self.color_print("❌ 停止ngrok失败", "red")

        # 停止API
        if self.api_process and self.api_process.poll() is None:
            self.color_print("停止API服务...", "yellow")
            try:
                self.api_process.terminate()
                self.api_process.wait(timeout=5)
                self.color_print("✅ API服务已停止", "green")
                stopped = True
            except:
                self.color_print("❌ 停止API服务失败", "red")

        if stopped:
            self.running = False
            self.ngrok_url = None
            time.sleep(1)
        else:
            self.color_print("⚠️  没有正在运行的服务", "yellow")

    def open_test_pages(self):
        """打开测试页面"""
        self.color_print("\n🌐 打开测试页面...", "yellow")

        # 打开本地测试页面
        local_urls = [
            f"http://localhost:{self.api_port}",
            f"http://localhost:{self.api_port}/api/health",
            f"http://localhost:{self.api_port}/api/activities?limit=5"
        ]

        for url in local_urls:
            try:
                webbrowser.open(url)
                print(f"✅ 已打开: {url}")
                time.sleep(0.5)
            except:
                print(f"❌ 无法打开: {url}")

        # 如果ngrok运行中，也打开公网测试
        if self.ngrok_url:
            try:
                webbrowser.open(f"{self.ngrok_url}/api/health")
                print(f"✅ 已打开公网测试: {self.ngrok_url}/api/health")
            except:
                print(f"❌ 无法打开公网测试")

    def show_coze_guide(self):
        """显示Coze插件配置指南"""
        self.color_print("\n🤖 Coze插件配置指南", "cyan", True)
        print("=" * 70)

        if self.ngrok_url:
            self.color_print(f"服务地址: {self.ngrok_url}", "green", True)
        else:
            self.color_print("服务地址: [请先启动ngrok隧道]", "yellow")

        print("\n配置步骤:")
        self.color_print("1. 登录Coze平台: https://www.coze.cn/", "white")
        self.color_print("2. 进入'工作台' → '插件' → '创建插件'", "white")
        self.color_print("3. 填写插件信息:", "white")
        print("   - 插件名称: 西安活动日历爬虫")
        print("   - 描述: 爬取西安本地宝的活动日历信息")
        print(f"   - 服务地址: {self.ngrok_url if self.ngrok_url else '[ngrok URL]'}")
        print("   - 认证方式: 无认证")

        self.color_print("\n4. 添加API端点:", "white")
        print("   - /api/health (GET) - 健康检查")
        print("   - /api/activities (GET) - 获取活动")
        print("     * 参数: limit (可选, 限制返回数量)")
        print("     * 参数: save (可选, 是否保存到文件)")
        print("   - /api/activities/count (GET) - 获取活动数量")

        self.color_print("\n5. 创建技能:", "white")
        print("   - 技能名称: 西安活动查询助手")
        print("   - 描述: 查询西安最新的活动信息")
        print("   - 关联刚创建的插件")

        self.color_print("\n6. 测试对话:", "white")
        print("   - '西安最近有什么活动?'")
        print("   - '帮我查一下西安本周末的活动'")
        print("   - '西安有什么音乐节或展览?'")

        print("=" * 70)

    def cleanup(self):
        """清理函数，在退出时调用"""
        self.color_print("\n🧹 正在清理...", "yellow")
        self.stop_all_services()

    def run(self):
        """运行服务管理器"""
        self.print_header()

        # 注册退出时的清理函数
        atexit.register(self.cleanup)

        # 捕获Ctrl+C
        signal.signal(signal.SIGINT, self.signal_handler)

        while True:
            self.print_menu()

            try:
                choice = input("\n请选择操作 (1-9): ").strip()

                if choice == '1':
                    self.start_api_service(show_output=True)
                elif choice == '2':
                    self.start_ngrok_tunnel()
                elif choice == '3':
                    if self.start_api_service(show_output=False):
                        time.sleep(2)
                        self.start_ngrok_tunnel()
                elif choice == '4':
                    self.test_connections()
                elif choice == '5':
                    self.show_status()
                elif choice == '6':
                    self.stop_all_services()
                elif choice == '7':
                    self.open_test_pages()
                elif choice == '8':
                    self.show_coze_guide()
                elif choice == '9':
                    self.color_print("\n👋 退出服务管理器", "cyan")
                    break
                else:
                    self.color_print("❌ 无效选择，请重新输入", "red")

                input("\n按回车键继续...")

            except KeyboardInterrupt:
                self.color_print("\n\n⚠️  检测到中断请求", "yellow")
                confirm = input("是否要退出服务管理器? (y/n): ").strip().lower()
                if confirm == 'y':
                    break
            except Exception as e:
                self.color_print(f"❌ 发生错误: {e}", "red")
                time.sleep(2)

        # 清理
        self.cleanup()

    def signal_handler(self, sig, frame):
        """信号处理函数"""
        self.color_print("\n\n⚠️  检测到Ctrl+C，正在停止服务...", "yellow")
        self.cleanup()
        sys.exit(0)


def main():
    """主函数"""
    # 检查依赖
    try:
        import requests
        import flask
    except ImportError as e:
        print(f"❌ 缺少依赖: {e}")
        print("请安装依赖: pip install Flask requests")
        return

    # 运行服务管理器
    manager = ServiceManager()
    manager.run()


if __name__ == "__main__":
    main()