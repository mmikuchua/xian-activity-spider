import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from bs4 import BeautifulSoup


def scrape_sxlib_lectures():
    """
    爬取陕西省图书馆 "陕图讲坛" 的讲座活动信息
    返回：包含讲座信息的列表，每个元素为字典 {'title': '讲座标题', 'url': '详情链接', 'date': '讲座日期'}
    """
    url = "https://www.sxlib.org.cn/hd/hdyg/stjt/"
    driver = None
    lectures = []

    try:
        # 1. 配置 Chrome 浏览器选项（无头模式，不显示界面）
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # 无头模式
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        # 设置 User-Agent 避免被屏蔽
        chrome_options.add_argument(
            "user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36")

        # 2. 启动浏览器驱动（需提前配置好 chromedriver 环境变量）
        driver = webdriver.Chrome(options=chrome_options)
        driver.get(url)

        # 3. 等待列表加载完成（等待 ul#zebra 元素出现，最多等待 10 秒）
        wait = WebDriverWait(driver, 10)
        ul_element = wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "ul#zebra")))

        # 4. 获取页面源代码并交给 BeautifulSoup 解析
        soup = BeautifulSoup(driver.page_source, "html.parser")
        ul = soup.find("ul", id="zebra")

        if not ul:
            print("未找到 id 为 'zebra' 的 ul 元素，请检查页面结构")
            return lectures

        # 5. 遍历所有 li 元素，提取信息
        for li in ul.find_all("li", recursive=False):  # recursive=False 只获取直接子元素
            # 提取活动详情页链接
            a_tag = li.find("a")
            if a_tag and a_tag.get("href"):
                href = a_tag["href"]
                # 处理相对路径
                if not href.startswith("http"):
                    href = "https://www.sxlib.org.cn" + href
            else:
                href = ""

            # 提取活动名称（位于 <font> 标签内）
            font_tag = li.find("font")
            title = font_tag.get_text(strip=True) if font_tag else ""

            # 提取活动时间（位于 <span> 标签内）
            span_tag = li.find("span")
            date = span_tag.get_text(strip=True) if span_tag else ""

            if title or href or date:
                lectures.append({
                    "title": title,
                    "url": href,
                    "date": date
                })

        print(f"成功抓取 {len(lectures)} 条讲座信息")
        return lectures

    except Exception as e:
        print(f"爬取过程中发生错误: {e}")
        return []
    finally:
        if driver:
            driver.quit()  # 关闭浏览器


if __name__ == "__main__":
    data = scrape_sxlib_lectures()
    for idx, item in enumerate(data, 1):
        print(f"{idx}. {item['title']}")
        print(f"   时间: {item['date']}")
        print(f"   链接: {item['url']}\n")