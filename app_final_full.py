from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd
import time
import os
import uuid

app = FastAPI(title="西安本地宝活动日历爬虫API")
OUTPUT_DIR = "./output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


def run_full_xian_spider():
    """
    这是您原始爬虫代码的完整移植，一行功能都不少！
    返回抓取到的 pandas DataFrame 和所有输出文件。
    """
    # ================= 配置部分 (完全保留) =================
    TARGET_URL = 'https://xa.bendibao.com/xiuxian/huodongrili/'

    # 定义输出表格的表头 (中文，将作为CSV的列名)
    TABLE_HEADERS = {
        'title': '活动名称',
        'time': '活动时间',
        'address': '活动地址',
        'highlights': '活动亮点',
        'guide_link': '攻略链接',
        'source': '数据来源'
    }

    # ================= 主程序 =================
    print("🚀 西安本地宝活动日历 - 完整数据抓取")
    print("=" * 60)

    driver = None
    try:
        # 1. 启动浏览器 (完全保留)
        print("1. 正在启动浏览器...")
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless')  # 调试时可注释掉，看到浏览器操作
        options.add_argument('--disable-gpu')

        # 使用webdriver_manager自动管理驱动，避免版本问题
        # 指定本地ChromeDriver的绝对路径
        # 指定本地ChromeDriver的绝对路径
        driver_path = r'C:\Users\33226\Desktop\MyXianSpiderBot\chromedriver.exe'  # 请替换为真实路径
        service = Service(executable_path=driver_path)
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(10)

        # 2. 访问页面
        print(f"2. 访问页面: {TARGET_URL}")
        driver.get(TARGET_URL)

        # 3. 确保页面加载
        print("3. 等待页面初始化...")
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "main-block-single")))

        # 4. 模拟点击"展开更多"按钮 (完整保留循环逻辑)
        print("4. 开始加载完整数据 (模拟点击'展开更多')...")
        click_count = 0
        max_clicks = 30  # 安全上限

        while click_count < max_clicks:
            try:
                show_more_btn = driver.find_element(By.ID, "showmore1")

                if show_more_btn.is_displayed():
                    click_count += 1
                    print(f"   点击第 {click_count} 次...")

                    # 滚动到按钮并点击
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_more_btn)
                    time.sleep(0.5)
                    show_more_btn.click()

                    # 等待新内容加载
                    time.sleep(2.5)
                else:
                    print("   '展开更多'按钮已不可见，加载可能完成。")
                    break

            except NoSuchElementException:
                print("   未找到'展开更多'按钮，可能所有内容已加载完毕。")
                break
            except Exception as e:
                print(f"   点击时出现异常: {e}")
                break

        print(f"   点击完成，共尝试 {click_count} 次。")
        print("5. 等待最终页面稳定...")
        time.sleep(3)

        # 5. 获取完整页面源码
        full_html = driver.page_source

        # 6. 解析并提取数据
        print("6. 解析页面并提取活动信息...")
        soup = BeautifulSoup(full_html, 'html.parser')
        activity_containers = soup.find_all('div', class_='main-block-single')
        print(f"   ✅ 共找到 {len(activity_containers)} 个活动")

        if len(activity_containers) == 0:
            print("警告：未找到任何活动信息。")
            return pd.DataFrame()  # 返回空DataFrame

        # 7. 提取每个活动的详细信息 (完整保留每个字段的提取逻辑)
        all_activities_data = []

        for idx, container in enumerate(activity_containers, 1):
            # 初始化一个活动字典，使用TABLE_HEADERS中定义的键
            activity = {'index': idx}

            # 提取活动名称
            title_elem = container.find(class_='main-single-block-titles')
            activity['title'] = title_elem.get_text(strip=True) if title_elem else '未获取'

            # 提取活动时间
            time_elem = container.find(class_='time-dia-hover')
            activity['time'] = time_elem.get_text(strip=True) if time_elem else '未获取'

            # 提取活动地址 (完整保留搜索逻辑)
            address_div = None
            for div in container.find_all('div', class_='main-single-block-msg'):
                if div.find('span', class_='main-single-block-des') and '活动地址' in div.get_text():
                    address_div = div
                    break
            if address_div:
                spans = address_div.find_all('span')
                activity['address'] = spans[1].get_text(strip=True) if len(spans) > 1 else '未获取'
            else:
                activity['address'] = '未获取'

            # 提取活动亮点 (完整保留搜索逻辑)
            highlight_div = None
            for div in container.find_all('div', class_='main-single-block-msg'):
                if div.find('span', class_='main-single-block-des') and '活动亮点' in div.get_text():
                    highlight_div = div
                    break
            if highlight_div:
                spans = highlight_div.find_all('span')
                activity['highlights'] = spans[1].get_text(strip=True) if len(spans) > 1 else '未获取'
            else:
                activity['highlights'] = '未获取'

            # 提取攻略链接
            guide_link_elem = container.find('a', class_='ticket-buttons')
            if guide_link_elem and guide_link_elem.get('href'):
                link = guide_link_elem['href']
                if link.startswith('/'):
                    link = 'https://xa.bendibao.com' + link
                activity['guide_link'] = link
            else:
                activity['guide_link'] = '无'

            # 添加数据来源标识
            activity['source'] = '西安本地宝'

            all_activities_data.append(activity)

        # 8. 转换为DataFrame，并应用自定义表头 (完整保留转换逻辑)
        df = pd.DataFrame(all_activities_data)

        # 重命名列，使用自定义表头
        rename_dict = {key: TABLE_HEADERS.get(key, key) for key in df.columns if key != 'index'}
        df.rename(columns=rename_dict, inplace=True)

        # 设置序号列
        df.index = df.pop('index')
        df.index.name = '序号'

        # 9. 显示数据预览 (完整保留显示选项)
        print("\n" + "=" * 100)
        print("活动数据预览 (前10行)")
        print("=" * 100)

        # 设置显示选项，确保完整显示
        with pd.option_context('display.max_rows', 10,
                               'display.max_columns', None,
                               'display.width', None,
                               'display.max_colwidth', 25):
            print(df.head(10))

        if len(df) > 10:
            print(f"... 以及另外 {len(df) - 10} 行数据")

        print("=" * 100)

        # 保存所有文件到本地（与原始代码完全一致）
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        base_filename = f'西安本地宝活动_{timestamp}'

        # 10. 保存数据到文件
        # CSV文件 (Excel可打开)
        csv_filename = f'{base_filename}.csv'
        df.to_csv(csv_filename, encoding='utf-8-sig')  # utf-8-sig确保Excel中文不乱码
        print(f"✅ 数据已保存为 CSV 文件: {csv_filename}")

        # Excel文件 (完整保留异常处理)
        try:
            excel_filename = f'{base_filename}.xlsx'
            df.to_excel(excel_filename, index=True, engine='openpyxl')
            print(f"✅ 数据已保存为 Excel 文件: {excel_filename}")
        except ImportError:
            print("ℹ️  如需保存为Excel格式，请安装: pip install openpyxl")
        except Exception as e:
            print(f"ℹ️  Excel保存跳过: {e}")

        # 详细文本文件 (完整保留格式化)
        txt_filename = f'{base_filename}.txt'
        with open(txt_filename, 'w', encoding='utf-8') as f:
            f.write("西安本地宝 - 活动日历完整列表\n")
            f.write(f"抓取时间: {time.strftime('%Y-%m-%d %H:%M:%S')}\n")
            f.write(f"活动总数: {len(df)}\n")
            f.write("=" * 80 + "\n\n")

            for _, activity in enumerate(all_activities_data, 1):
                f.write(f"【活动 {activity['index']}】\n")
                f.write(f"  活动名称: {activity['title']}\n")
                f.write(f"  活动时间: {activity['time']}\n")
                f.write(f"  活动地址: {activity['address']}\n")
                if len(activity['highlights']) > 100:
                    f.write(f"  活动亮点: {activity['highlights'][:100]}...\n")
                else:
                    f.write(f"  活动亮点: {activity['highlights']}\n")
                f.write(f"  攻略链接: {activity['guide_link']}\n")
                f.write("-" * 60 + "\n")

        print(f"✅ 详细文本已保存: {txt_filename}")

        # 11. 数据统计摘要 (完整保留统计逻辑)
        print("\n📊 数据统计摘要")
        print(f"   活动总数: {len(df)}")
        if len(df) > 0:
            print(f"   时间跨度: {df['活动时间'].min()} 至 {df['活动时间'].max()}")
            print(f"   包含地址的活动: {df['活动地址'].ne('未获取').sum()}")
            print(f"   包含攻略链接的活动: {df['攻略链接'].ne('无').sum()}")

        print("\n🎉 抓取完成！")

        # 记录生成的文件名，供API使用
        return {
            'dataframe': df,
            'excel_file': excel_filename if 'excel_filename' in locals() else None,
            'csv_file': csv_filename,
            'txt_file': txt_filename,
            'count': len(df)
        }

    except Exception as e:
        print(f"\n❌ 程序运行出错: {e}")
        import traceback
        traceback.print_exc()
        return {'dataframe': pd.DataFrame(), 'error': str(e)}

    finally:
        if driver:
            driver.quit()
            print("🌐 浏览器已关闭。")


@app.get("/crawl")
async def crawl_activities(background_tasks: BackgroundTasks):
    """
    完整的API接口：触发完整爬虫并返回Excel文件。
    保留所有原始功能，包括控制台输出和本地文件保存。
    """
    try:
        print("=" * 60)
        print("🌐 收到API请求，开始执行完整爬虫...")
        print("=" * 60)

        # 执行完整的爬虫
        result = run_full_xian_spider()

        if result['dataframe'].empty:
            if 'error' in result:
                return {"detail": f"爬虫执行失败: {result['error']}"}
            return {"detail": "爬虫未能获取到数据"}

        # 生成API专用的Excel文件
        timestamp = time.strftime('%Y%m%d_%H%M%S')
        api_filename = f"西安本地宝活动_API返回_{timestamp}.xlsx"
        api_filepath = os.path.join(OUTPUT_DIR, api_filename)

        # 保存为Excel文件（包含完整格式）
        result['dataframe'].to_excel(api_filepath, index=True, engine='openpyxl')
        print(f"📤 API返回文件已生成: {api_filename}")

        # 统计信息
        print(f"📊 本次抓取统计:")
        print(f"   活动总数: {result['count']}")
        print(f"   Excel文件: {result.get('excel_file', '未生成')}")
        print(f"   CSV文件: {result.get('csv_file', '未生成')}")
        print(f"   TXT文件: {result.get('txt_file', '未生成')}")

        # 设置返回后自动清理临时文件（只清理API生成的，不清理原始爬虫生成的文件）
        background_tasks.add_task(os.remove, api_filepath)

        # 以文件流形式返回
        return FileResponse(
            path=api_filepath,
            filename=api_filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        print(f"❌ API处理失败: {e}")
        import traceback
        traceback.print_exc()
        return {"detail": f"服务器内部错误: {str(e)}"}


@app.get("/status")
def get_status():
    """获取最近一次爬虫的状态"""
    files = []
    if os.path.exists(OUTPUT_DIR):
        files = os.listdir(OUTPUT_DIR)

    return {
        "status": "running",
        "output_dir": OUTPUT_DIR,
        "file_count": len(files),
        "latest_files": sorted(files)[-5:] if files else []
    }


@app.get("/health")
def health_check():
    """健康检查端点"""
    return {
        "status": "healthy",
        "service": "xian-activity-spider-full",
        "timestamp": time.strftime('%Y-%m-%d %H:%M:%S')
    }


@app.get("/")
def home():
    return {
        "message": "西安本地宝活动日历完整爬虫API",
        "endpoints": {
            "/crawl": "触发完整爬虫并返回Excel文件",
            "/status": "查看爬虫状态和生成的文件",
            "/health": "健康检查",
            "/docs": "API文档"
        },
        "features": "完整保留原始爬虫的所有功能：数据预览、多格式保存、统计摘要等"
    }


if __name__ == "__main__":
    import uvicorn

    print("=" * 70)
    print("🚀 西安本地宝活动日历 - 完整爬虫API服务")
    print("=" * 70)
    print("📌 本服务完整保留原始爬虫的所有功能：")
    print("   ✅ 完整的数据提取和预览")
    print("   ✅ CSV、Excel、TXT三格式本地保存")
    print("   ✅ 详细统计摘要")
    print("   ✅ 完整的控制台日志输出")
    print("=" * 70)
    print("🌐 本地地址: http://127.0.0.1:8000")
    print("📊 状态查看: http://127.0.0.1:8000/status")
    print("🩺 健康检查: http://127.0.0.1:8000/health")
    print("📄 接口文档: http://127.0.0.1:8000/docs")
    print("🎯 触发爬虫: http://127.0.0.1:8000/crawl")
    print("=" * 70)

    uvicorn.run(app, host="127.0.0.1", port=8000)