from fastapi import FastAPI, BackgroundTasks
from fastapi.responses import FileResponse
import pandas as pd
import os
import uuid
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from bs4 import BeautifulSoup

app = FastAPI(title="西安本地宝活动爬虫API")
OUTPUT_DIR = "./output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

def run_xian_activity_spider():
    """
    这是你原来的爬虫逻辑，我将其封装为一个函数。
    返回抓取到的 pandas DataFrame。
    """
    TARGET_URL = 'https://xa.bendibao.com/xiuxian/huodongrili/'
    TABLE_HEADERS = {
        'title': '活动名称',
        'time': '活动时间',
        'address': '活动地址',
        'highlights': '活动亮点',
        'guide_link': '攻略链接',
        'source': '数据来源'
    }

    print("🚀 爬虫开始执行...")
    driver = None
    try:
        # 启动浏览器 (本地运行可以关闭headless方便调试)
        options = webdriver.ChromeOptions()
        # options.add_argument('--headless')  # 调试时可先注释，看到浏览器操作
        options.add_argument('--disable-gpu')
        # 可选：添加无痕模式，避免缓存干扰
        options.add_argument('--incognito')

        # 使用你指定的chromedriver路径
        service = Service(executable_path='./chromedriver.exe')
        driver = webdriver.Chrome(service=service, options=options)
        driver.implicitly_wait(10)

        # 访问页面
        print(f"访问页面: {TARGET_URL}")
        driver.get(TARGET_URL)

        # 等待页面加载
        print("等待页面初始化...")
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "main-block-single")))

        # 模拟点击“展开更多”按钮
        print("开始加载完整数据...")
        click_count = 0
        max_clicks = 30

        while click_count < max_clicks:
            try:
                show_more_btn = driver.find_element(By.ID, "showmore1")
                if show_more_btn.is_displayed():
                    click_count += 1
                    print(f"   点击第 {click_count} 次...")
                    driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", show_more_btn)
                    time.sleep(0.5)
                    show_more_btn.click()
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

        print(f"点击完成，共尝试 {click_count} 次。")
        time.sleep(3)

        # 解析页面
        soup = BeautifulSoup(driver.page_source, 'html.parser')
        activity_containers = soup.find_all('div', class_='main-block-single')
        print(f"✅ 共找到 {len(activity_containers)} 个活动")

        if len(activity_containers) == 0:
            print("警告：未找到任何活动信息。")
            return pd.DataFrame()  # 返回空DataFrame

        # 提取数据
        all_activities_data = []
        for idx, container in enumerate(activity_containers, 1):
            activity = {'index': idx}

            title_elem = container.find(class_='main-single-block-titles')
            activity['title'] = title_elem.get_text(strip=True) if title_elem else '未获取'

            time_elem = container.find(class_='time-dia-hover')
            activity['time'] = time_elem.get_text(strip=True) if time_elem else '未获取'

            address_div = None
            for div in container.find_all('div', class_='main-single-block-msg'):
                if div.find('span', class_='main-single-block-des') and '活动地址' in div.get_text():
                    address_div = div
                    break
            activity['address'] = address_div.find_all('span')[1].get_text(strip=True) if address_div and len(address_div.find_all('span')) > 1 else '未获取'

            highlight_div = None
            for div in container.find_all('div', class_='main-single-block-msg'):
                if div.find('span', class_='main-single-block-des') and '活动亮点' in div.get_text():
                    highlight_div = div
                    break
            activity['highlights'] = highlight_div.find_all('span')[1].get_text(strip=True) if highlight_div and len(highlight_div.find_all('span')) > 1 else '未获取'

            guide_link_elem = container.find('a', class_='ticket-buttons')
            if guide_link_elem and guide_link_elem.get('href'):
                link = guide_link_elem['href']
                activity['guide_link'] = 'https://xa.bendibao.com' + link if link.startswith('/') else link
            else:
                activity['guide_link'] = '无'

            activity['source'] = '西安本地宝'
            all_activities_data.append(activity)

        # 转换为DataFrame
        df = pd.DataFrame(all_activities_data)
        rename_dict = {key: TABLE_HEADERS.get(key, key) for key in df.columns if key != 'index'}
        df.rename(columns=rename_dict, inplace=True)
        df.index = df.pop('index')
        df.index.name = '序号'

        print(f"🎉 爬虫成功抓取 {len(df)} 条数据！")
        return df

    except Exception as e:
        print(f"❌ 爬虫运行出错: {e}")
        import traceback
        traceback.print_exc()
        return pd.DataFrame()
    finally:
        if driver:
            driver.quit()
            print("🌐 浏览器已关闭。")

@app.get("/crawl")
async def crawl_activities(background_tasks: BackgroundTasks):
    """
    核心API接口：触发爬虫并返回Excel文件。
    Coze工作流将调用此接口。
    """
    try:
        print("⏳ 收到请求，开始执行爬虫...")
        # 直接运行爬虫（同步函数，在FastAPI中运行耗时操作需注意）
        df = run_xian_activity_spider()

        if df.empty:
            # 如果爬虫返回空数据，返回一个友好的错误信息
            return {"detail": "爬虫未能获取到数据，可能网站结构已变化或网络异常。"}

        # 生成唯一文件名并保存
        filename = f"西安本地宝活动_{time.strftime('%Y%m%d_%H%M%S')}.xlsx"
        filepath = os.path.join(OUTPUT_DIR, filename)
        df.to_excel(filepath, index=True, engine='openpyxl')
        print(f"📁 文件已生成: {filepath}")

        # 设置文件返回后自动清理
        background_tasks.add_task(os.remove, filepath)

        # 以文件流形式返回
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        print(f"❌ API处理失败: {e}")
        return {"detail": f"服务器内部错误: {str(e)}"}

@app.get("/health")
def health_check():
    """健康检查端点"""
    return {"status": "healthy", "service": "xian-activity-spider", "time": time.time()}

@app.get("/")
def home():
    return {"message": "西安本地宝活动爬虫API已就绪，请访问 /crawl 触发爬取"}

if __name__ == "__main__":
    import uvicorn
    print("=" * 60)
    print("🚀 启动西安本地宝活动爬虫API")
    print("📌 本地地址: http://127.0.0.1:8000")
    print("📌 接口文档: http://127.0.0.1:8000/docs")
    print("=" * 60)
    uvicorn.run(app, host="127.0.0.1", port=8000)