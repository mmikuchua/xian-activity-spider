from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.edge.service import Service  # 改为Edge的Service
from selenium.webdriver.edge.options import Options  # 改为Edge的Options
from webdriver_manager.microsoft import EdgeChromiumDriverManager  # Edge驱动管理器
from bs4 import BeautifulSoup
import pandas as pd
import time
import os


def run_xian_spider():
    """
    运行西安本地宝活动日历爬虫的主函数。
    返回一个 pandas DataFrame。
    """
    # ================= 配置部分 =================
    TARGET_URL = 'https://xa.bendibao.com/xiuxian/huodongrili/'
    TABLE_HEADERS = {
        'title': '活动名称',
        'time': '活动时间',
        'address': '活动地址',
        'highlights': '活动亮点',
        'guide_link': '攻略链接',
        'source': '数据来源'
    }

    # ================= 主程序 =================
    print("🚀 开始执行爬虫 (使用Edge浏览器)...")
    driver = None
    try:
        # ========== 方案：使用Edge浏览器 ==========
        print("正在启动Microsoft Edge浏览器...")

        # 创建Edge选项
        options = Options()

        # 调试时先不使用无头模式，方便观察
        # options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--disable-blink-features=AutomationControlled')

        # 方法1：尝试使用webdriver-manager自动管理Edge驱动
        try:
            print("尝试自动获取Edge驱动...")
            service = Service(EdgeChromiumDriverManager().install())
            driver = webdriver.Edge(service=service, options=options)
            print("✅ 使用webdriver-manager成功启动Edge")

        except Exception as e:
            print(f"自动获取Edge驱动失败: {e}")
            print("尝试使用系统已安装的Edge...")

            # 方法2：手动指定Edge浏览器路径
            edge_paths = [
                r'C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe',  # 默认64位
                r'C:\Program Files\Microsoft\Edge\Application\msedge.exe',  # 可能的位置
                os.path.expanduser(r'~\AppData\Local\Microsoft\Edge\Application\msedge.exe')
            ]

            found_edge = False
            for edge_path in edge_paths:
                if os.path.exists(edge_path):
                    options.binary_location = edge_path
                    print(f"✅ 找到Edge浏览器: {edge_path}")
                    found_edge = True
                    break

            if not found_edge:
                print("❌ 未找到Edge浏览器，请确保已安装Microsoft Edge")
                print("您可以从 https://www.microsoft.com/edge 下载安装")
                return pd.DataFrame()

            # 尝试启动Edge
            try:
                # 首先尝试查找系统PATH中的msedgedriver
                driver = webdriver.Edge(options=options)
                print("✅ 使用系统Edge驱动成功启动")
            except Exception as driver_error:
                print(f"❌ Edge启动失败: {driver_error}")

                # 提供手动下载驱动的指引
                print("\n💡 解决方案：手动下载EdgeDriver")
                print("1. 查看Edge版本: 浏览器右上角 → 设置 → 关于Microsoft Edge")
                print("2. 访问: https://developer.microsoft.com/en-us/microsoft-edge/tools/webdriver/")
                print("3. 下载与您Edge版本匹配的驱动")
                print("4. 解压msedgedriver.exe，放到:")
                print("   - 项目文件夹内")
                print("   - 或 C:\\Windows\\System32\\")
                print("5. 然后重新运行测试")
                return pd.DataFrame()

        # ========== 后续爬虫逻辑（保持不变）==========
        driver.implicitly_wait(10)

        # 2. 访问页面
        print(f"🌐 访问页面: {TARGET_URL}")
        driver.get(TARGET_URL)
        time.sleep(2)

        # 3. 等待页面核心元素加载
        print("\n⏳ 等待页面加载...")
        try:
            # 等待页面标题包含关键词
            WebDriverWait(driver, 15).until(
                lambda d: "西安" in d.title or "活动" in d.title
            )
            print(f"✅ 页面标题: {driver.title}")
        except:
            print("⚠️ 页面标题等待超时，继续执行...")

        # 4. 检查页面是否加载成功
        page_html = driver.page_source
        if len(page_html) < 1000:
            print("❌ 页面内容异常，HTML过短")
            return pd.DataFrame()

        print(f"📄 页面大小: {len(page_html)} 字符")

        # 5. 查找活动容器
        print("\n🔍 开始查找活动容器...")
        soup = BeautifulSoup(page_html, 'html.parser')

        # 调试：查看页面中的div数量
        all_divs = soup.find_all('div')
        print(f"页面中共有 {len(all_divs)} 个div元素")

        # 查找可能的容器类
        activity_containers = []
        possible_classes = ['main-block-single', 'block-single', 'list-item', 'item']

        for class_name in possible_classes:
            containers = soup.find_all('div', class_=class_name)
            if containers:
                print(f"✅ 使用类名 '{class_name}' 找到了 {len(containers)} 个容器")
                activity_containers = containers
                break

        # 如果没找到，尝试更通用的选择器
        if not activity_containers:
            print("⚠️ 未找到标准类名的容器，尝试其他选择器...")
            # 查找包含活动相关文本的div
            activity_keywords = ['活动', 'event', 'activity', '时间', '地址']
            for keyword in activity_keywords:
                containers = soup.find_all('div', string=lambda text: text and keyword in text)
                if containers:
                    print(f"✅ 通过关键词 '{keyword}' 找到 {len(containers)} 个相关元素")
                    activity_containers = containers
                    break

        print(f"\n📊 最终确定的活动容器数量: {len(activity_containers)}")

        if len(activity_containers) == 0:
            print("\n❌ 未找到任何活动容器！")
            print("正在分析页面结构...")

            # 打印前20个div的结构
            print("\n页面中前20个div的class属性:")
            for i, div in enumerate(all_divs[:20]):
                class_attr = div.get('class', [])
                text_preview = div.get_text(strip=True)[:50] if div.get_text(strip=True) else "空"
                print(f"  {i + 1:2d}. class: {class_attr}, text: {text_preview}...")

            return pd.DataFrame()

        # 6. 提取每个活动的详细信息并详细打印
        print("\n" + "=" * 80)
        print("📋 开始提取活动详细信息")
        print("=" * 80)

        all_activities_data = []

        for idx, container in enumerate(activity_containers, 1):
            print(f"\n{'━' * 40}")
            print(f"活动 #{idx:2d}")
            print(f"{'━' * 40}")

            activity = {'index': idx}

            # 首先打印整个容器的文本内容（前200字符）
            container_text = container.get_text(strip=True)
            print(f"容器文本预览: {container_text[:200]}...")

            try:
                # --- 提取活动名称 ---
                title_elem = container.find(class_='main-single-block-titles')
                if not title_elem:
                    # 尝试查找h1-h4标题
                    for tag in ['h1', 'h2', 'h3', 'h4']:
                        title_elem = container.find(tag)
                        if title_elem:
                            break

                activity_title = title_elem.get_text(strip=True) if title_elem else f'未命名活动_{idx}'
                activity['title'] = activity_title
                print(f"📌 活动名称: {activity_title}")

                # --- 提取活动时间 ---
                time_elem = container.find(class_='time-dia-hover')
                if not time_elem:
                    # 查找包含"时间"的元素
                    time_elems = container.find_all(string=lambda text: text and '时间' in text)
                    if time_elems:
                        time_elem = time_elems[0].parent if time_elems[0].parent else time_elems[0]

                activity_time = time_elem.get_text(strip=True) if time_elem else '时间未定'
                activity['time'] = activity_time
                print(f"🕒 活动时间: {activity_time}")

                # --- 提取活动地址 ---
                address_text = '地址未定'
                address_div = None

                # 查找包含"地址"的div
                for div in container.find_all('div'):
                    if '地址' in div.get_text():
                        address_div = div
                        break

                if address_div:
                    # 查找地址文本（排除"活动地址"标签）
                    for elem in address_div.find_all(['span', 'div', 'p']):
                        text = elem.get_text(strip=True)
                        if text and '地址' not in text and len(text) > 2:
                            address_text = text
                            break

                activity['address'] = address_text
                print(f"📍 活动地址: {address_text}")

                # --- 提取活动亮点 ---
                highlight_text = '暂无亮点'
                for div in container.find_all('div'):
                    if '亮点' in div.get_text():
                        # 查找亮点描述
                        for elem in div.find_all(['span', 'div', 'p']):
                            text = elem.get_text(strip=True)
                            if text and '亮点' not in text and len(text) > 2:
                                highlight_text = text[:100]  # 截断避免过长
                                break
                        break

                activity['highlights'] = highlight_text
                print(f"✨ 活动亮点: {highlight_text}")

                # --- 提取攻略链接 ---
                link = '无'
                for a_tag in container.find_all('a', href=True):
                    href = a_tag['href']
                    if href and not href.startswith('javascript:'):
                        if href.startswith('/'):
                            link = f'https://xa.bendibao.com{href}'
                        else:
                            link = href
                        break

                activity['guide_link'] = link
                print(f"🔗 攻略链接: {link}")

                # --- 数据来源 ---
                activity['source'] = '西安本地宝'
                print(f"🏷️  数据来源: 西安本地宝")

                all_activities_data.append(activity)
                print(f"✅ 活动 #{idx} 提取完成")

            except Exception as e:
                print(f"❌ 活动 #{idx} 提取失败: {str(e)}")
                # 即使失败也添加一个基础记录
                base_activity = {
                    'index': idx,
                    'title': f'解析失败的活动_{idx}',
                    'time': '解析失败',
                    'address': '解析失败',
                    'highlights': '解析失败',
                    'guide_link': '无',
                    'source': '西安本地宝'
                }
                all_activities_data.append(base_activity)
                continue

        # 7. 转换为DataFrame
        print("\n" + "=" * 80)
        print("📊 数据汇总")
        print("=" * 80)

        if not all_activities_data:
            print("❌ 未能提取到任何活动数据！")
            return pd.DataFrame()

        df = pd.DataFrame(all_activities_data)
        rename_dict = {key: TABLE_HEADERS.get(key, key) for key in df.columns if key != 'index'}
        df.rename(columns=rename_dict, inplace=True)
        df.index = df.pop('index')
        df.index.name = '序号'

        print(f"\n🎉 成功抓取 {len(df)} 条活动数据！")

        # 打印完整的DataFrame
        print("\n完整数据表格:")
        print("-" * 100)

        # 设置pandas显示选项，确保显示所有列和完整内容
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', 40)

        print(df)
        print("-" * 100)

        # 打印数据统计
        print("\n📈 数据统计:")
        print(f"  活动总数: {len(df)}")
        if len(df) > 0:
            print(f"  列数: {len(df.columns)}")
            print(f"  列名: {list(df.columns)}")

            # 统计有效数据
            valid_address = df['活动地址'].str.contains('未定|失败').sum()
            valid_links = df['攻略链接'].str.contains('无').sum()
            print(f"  地址有效的数据: {len(df) - valid_address}/{len(df)}")
            print(f"  有链接的数据: {len(df) - valid_links}/{len(df)}")

        return df

    except Exception as e:
        print(f"\n❌ 爬虫运行出错: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    finally:
        # 确保浏览器总是被关闭
        if driver:
            driver.quit()
            print("\n🌐 浏览器已关闭。")