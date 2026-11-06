# -*- coding: utf-8 -*-
from flask import Flask, jsonify, request
from flask_cors import CORS
import json
import time
import os
import traceback
import pandas as pd
from datetime import datetime
import logging
from urllib.parse import urljoin
import threading  # 新增：用于并发控制

# ---------- Selenium 相关导入 ----------
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.action_chains import ActionChains
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import NoSuchElementException, TimeoutException
from bs4 import BeautifulSoup

# ---------- Flask 应用初始化 ----------
app = Flask(__name__)
CORS(app)

# ---------- 全局并发锁（防止多个爬虫同时运行）----------
scrape_lock = threading.Lock()


# ========== 1. 西安本地宝爬虫（完全不变）==========
def scrape_activities(save_to_file=False):
    """爬取西安本地宝活动数据"""
    print("🚀 开始爬取活动数据...")
    target_url = 'https://xa.bendibao.com/xiuxian/huodongrili/'
    table_headers = {
        'title': '活动名称',
        'time': '活动时间',
        'address': '活动地址',
        'highlights': '活动亮点',
        'guide_link': '攻略链接',
        'source': '数据来源'
    }
    driver = None
    result = {
        'status': 'success',
        'message': '',
        'data': [],
        'metadata': {},
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }

    def extract_detail(container, keyword):
        for div in container.find_all('div', class_='main-single-block-msg'):
            if div.find('span', class_='main-single-block-des') and keyword in div.get_text():
                spans = div.find_all('span')
                return spans[1].get_text(strip=True) if len(spans) > 1 else '未获取'
        return '未获取'

    try:
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.implicitly_wait(10)

        driver.get(target_url)
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "main-block-single")))

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
                    break
            except NoSuchElementException:
                break
            except Exception:
                break

        time.sleep(3)
        full_html = driver.page_source
        soup = BeautifulSoup(full_html, 'html.parser')
        activity_containers = soup.find_all('div', class_='main-block-single')
        print(f"   ✅ 共找到 {len(activity_containers)} 个活动")

        all_activities_data = []
        for idx, container in enumerate(activity_containers, 1):
            activity = {'index': idx}
            title_elem = container.find(class_='main-single-block-titles')
            activity['title'] = title_elem.get_text(strip=True) if title_elem else '未获取'
            time_elem = container.find(class_='time-dia-hover')
            activity['time'] = time_elem.get_text(strip=True) if time_elem else '未获取'

            activity['address'] = extract_detail(container, '活动地址')
            activity['highlights'] = extract_detail(container, '活动亮点')

            guide_link_elem = container.find('a', class_='ticket-buttons')
            if guide_link_elem and guide_link_elem.get('href'):
                link = guide_link_elem['href']
                if link.startswith('/'):
                    link = 'https://xa.bendibao.com' + link
                activity['guide_link'] = link
            else:
                activity['guide_link'] = '无'

            activity['source'] = '西安本地宝'
            activity['id'] = f"act_{idx}_{int(time.time())}"
            all_activities_data.append(activity)

        df = pd.DataFrame(all_activities_data)
        rename_dict = {key: table_headers.get(key, key) for key in df.columns if key not in ['index', 'id']}
        df.rename(columns=rename_dict, inplace=True)

        if save_to_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_filename = f'西安本地宝活动_{timestamp}.csv'
            df.to_csv(csv_filename, encoding='utf-8-sig', index=False)
            json_filename = f'西安本地宝活动_{timestamp}.json'
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(all_activities_data, f, ensure_ascii=False, indent=2)

        result['data'] = all_activities_data
        result['metadata'] = {
            'total_count': len(all_activities_data),
            'scrape_time': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
            'click_count': click_count,
            'has_address_count': sum(1 for act in all_activities_data if act['address'] != '未获取'),
            'has_guide_count': sum(1 for act in all_activities_data if act['guide_link'] != '无')
        }
        result['message'] = f'成功爬取 {len(all_activities_data)} 个活动'
        print(f"\n🎉 爬取完成！共获取 {len(all_activities_data)} 个活动")
    except Exception as e:
        print(f"\n❌ 爬虫运行出错: {e}")
        result['status'] = 'error'
        result['message'] = str(e)
        traceback.print_exc()
    finally:
        if driver:
            driver.quit()
            print("🌐 浏览器已关闭。")
    return result


# ========== 2. 陕西大剧院（SNPAC）爬虫（完全不变）==========
def scrape_snpac(max_items=None):
    """爬取陕西大剧院演出信息（支持 max_items 逐个爬取）"""
    logger = logging.getLogger(__name__)
    base_url = "https://www.snpac.com/sxtheatre/index.html"

    options = webdriver.ChromeOptions()
    options.add_experimental_option("excludeSwitches", ["enable-automation"])
    options.add_experimental_option('useAutomationExtension', False)
    options.add_argument('--disable-blink-features=AutomationControlled')
    driver = webdriver.Chrome(options=options)

    def safe_click(web_driver, element):
        try:
            web_driver.execute_script("arguments[0].scrollIntoView({block: 'center'});", element)
            time.sleep(0.3)
            ActionChains(web_driver).click(element).perform()
            return True
        except Exception:
            try:
                web_driver.execute_script("arguments[0].click();", element)
                return True
            except Exception:
                return False

    def enter_performance_list(web_driver):
        enter_selectors = [
            "//a[contains(text(),'全部演出')]",
            "//span[contains(text(),'全部演出')]",
            "//div[contains(text(),'全部演出')]",
            "//a[contains(text(),'演出')]",
            "//span[contains(text(),'演出')]",
            "//a[contains(@href,'#/index')]",
            "//*[contains(@class,'nav')]//a[contains(text(),'演出')]"
        ]
        for xpath in enter_selectors:
            try:
                btn = WebDriverWait(web_driver, 3).until(
                    EC.element_to_be_clickable((By.XPATH, xpath))
                )
                btn.click()
                logger.info(f"✅ 点击进入列表: {xpath}")
                time.sleep(2)
                return True
            except Exception:
                continue
        logger.warning("⚠️ 未找到明确的'全部演出'按钮")
        return False

    def extract_card_info(card):
        info = {}
        try:
            name_elem = card.find_element(By.CSS_SELECTOR, "[class*='program-name']")
            info['name'] = name_elem.text.strip()
        except Exception:
            info['name'] = ''
        try:
            type_elem = card.find_element(By.CSS_SELECTOR, "[class*='tip-text']")
            info['type'] = type_elem.text.strip()
        except Exception:
            info['type'] = ''
        try:
            address_elem = card.find_element(By.CSS_SELECTOR, "[class*='address']")
            info['address'] = address_elem.text.strip()
        except Exception:
            info['address'] = ''
        try:
            price_elem = card.find_element(By.CSS_SELECTOR, "[class*='price-part']")
            info['price'] = price_elem.text.strip()
        except Exception:
            info['price'] = ''
        try:
            time_elem = card.find_element(By.CSS_SELECTOR, "[class*='year']")
            info['time'] = time_elem.text.strip()
        except Exception:
            info['time'] = ''
        return info

    def restore_homepage(web_driver):
        web_driver.get(f"{base_url}#/index")
        WebDriverWait(web_driver, 10).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='program']"))
        )
        time.sleep(1)

    performances = []
    clicked_titles = set()
    attempt = 0
    max_attempts = 50

    try:
        driver.get(f"{base_url}#/index")
        driver.maximize_window()
        WebDriverWait(driver, 20).until(EC.presence_of_element_located((By.TAG_NAME, "body")))
        enter_performance_list(driver)
        WebDriverWait(driver, 15).until(
            EC.presence_of_element_located((By.CSS_SELECTOR, "div[class*='program']"))
        )
        time.sleep(1)

        while attempt < max_attempts:
            if max_items is not None and len(performances) >= max_items:
                logger.info(f"✅ 已达到指定爬取数量 {max_items}，提前结束")
                break

            attempt += 1
            cards = driver.find_elements(By.CSS_SELECTOR, "div[class*='program']")
            if not cards:
                break

            target_card = None
            target_title = ""
            for card in cards:
                try:
                    title_elem = card.find_element(By.CSS_SELECTOR, "h3, h4, [class*='title'], [class*='name']")
                    title_text = title_elem.text.strip()
                    if title_text and title_text not in clicked_titles:
                        target_card = card
                        target_title = title_text
                        break
                except Exception:
                    continue

            if not target_card:
                break

            card_info = extract_card_info(target_card)
            try:
                before_url = driver.current_url
                if not safe_click(driver, target_card):
                    logger.warning(f"点击失败: {target_title[:20]}")
                    clicked_titles.add(target_title)
                    restore_homepage(driver)
                    continue

                time.sleep(2)
                current_url = driver.current_url
                if "/ticket/detail/" in current_url and current_url != before_url:
                    performance_record = {
                        'url': current_url,
                        'name': card_info.get('name', ''),
                        'type': card_info.get('type', ''),
                        'address': card_info.get('address', ''),
                        'price': card_info.get('price', ''),
                        'time': card_info.get('time', '')
                    }
                    performances.append(performance_record)
                    logger.info(f"✅ [{len(performances)}] {card_info['name'][:20]}")

                clicked_titles.add(target_title)
                restore_homepage(driver)

            except Exception as e:
                logger.warning(f"处理出错: {str(e)[:50]}")
                clicked_titles.add(target_title)
                restore_homepage(driver)
                continue

    finally:
        driver.quit()

    return performances


# ========== 3. API 路由（已加锁）==========
@app.route('/')
def home():
    return jsonify({
        'service': '西安本地宝活动爬虫API',
        'version': '1.0.0',
        'endpoints': {
            '/api/activities': '获取所有活动数据',
            '/api/activities/latest': '获取最新爬取的数据',
            '/api/activities/count': '获取活动数量',
            '/api/health': '健康检查',
            '/api/snpac/scrape': '陕西大剧院演出爬虫（支持?max=1逐个爬取）'
        }
    })


@app.route('/api/activities', methods=['GET'])
def get_activities():
    if not scrape_lock.acquire(blocking=False):
        return jsonify({'status': 'error', 'message': '另一个爬虫正在运行，请稍后重试'}), 429
    try:
        save_file = request.args.get('save', 'false').lower() == 'true'
        limit = request.args.get('limit', type=int)
        result = scrape_activities(save_to_file=save_file)
        if limit and result['status'] == 'success':
            result['data'] = result['data'][:limit]
            result['metadata']['returned_count'] = len(result['data'])
        return jsonify(result), 200 if result['status'] != 'error' else 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': f'API处理错误: {str(e)}'}), 500
    finally:
        scrape_lock.release()


@app.route('/api/activities/latest', methods=['GET'])
def get_latest_activities():
    if not scrape_lock.acquire(blocking=False):
        return jsonify({'status': 'error', 'message': '另一个爬虫正在运行，请稍后重试'}), 429
    try:
        limit = request.args.get('limit', 10, type=int)
        result = scrape_activities(save_to_file=False)
        if result['status'] == 'success':
            latest_data = result['data'][:limit]
            return jsonify({
                'status': 'success',
                'message': f'获取最新 {len(latest_data)} 个活动',
                'data': latest_data,
                'total_available': len(result['data']),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }), 200
        else:
            return jsonify(result), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        scrape_lock.release()


@app.route('/api/activities/count', methods=['GET'])
def get_activities_count():
    if not scrape_lock.acquire(blocking=False):
        return jsonify({'status': 'error', 'message': '另一个爬虫正在运行，请稍后重试'}), 429
    try:
        result = scrape_activities(save_to_file=False)
        if result['status'] == 'success':
            return jsonify({
                'status': 'success',
                'total_activities': len(result['data']),
                'metadata': result.get('metadata', {}),
                'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
            }), 200
        else:
            return jsonify(result), 500
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        scrape_lock.release()


@app.route('/api/health', methods=['GET'])
def health_check():
    # 健康检查不需要锁
    return jsonify({
        'status': 'healthy',
        'service': 'activity-scraper-api',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }), 200


@app.route('/api/test', methods=['GET'])
def test_endpoint():
    # 测试端点不需要锁
    return jsonify({
        'status': 'success',
        'message': 'API服务正常运行',
        'test_data': [{
            'id': 'test_001',
            'title': '测试活动 - 音乐节',
            'time': '2024-01-01 19:00',
            'address': '西安大唐不夜城',
            'highlights': '知名乐队现场演出',
            'guide_link': 'https://example.com/guide',
            'source': '测试数据'
        }],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }), 200


@app.route('/api/snpac/scrape', methods=['GET'])
def snpac_scrape():
    if not scrape_lock.acquire(blocking=False):
        return jsonify({'status': 'error', 'message': '另一个爬虫正在运行，请稍后重试'}), 429
    try:
        max_items = request.args.get('max', default=None, type=int)
        save_file = request.args.get('save', 'false').lower() == 'true'
        data = scrape_snpac(max_items=max_items)
        if save_file and data:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            filename = f'snpac_演出_{timestamp}.json'
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, ensure_ascii=False, indent=2)
        return jsonify({
            'status': 'success',
            'count': len(data),
            'data': data,
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 200
    except Exception as e:
        return jsonify({'status': 'error', 'message': str(e)}), 500
    finally:
        scrape_lock.release()


# ========== 4. 启动入口 ==========
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))
    print("=" * 60)
    print("🚀 活动爬虫API服务（双爬虫版 + 并发锁）")
    print(f"📡 服务启动在: http://localhost:{port}")
    print("=" * 60)
    print("可用端点:")
    print("  /                           - 服务首页")
    print("  /api/activities            - 西安本地宝活动（支持?limit）")
    print("  /api/activities/latest     - 最新活动")
    print("  /api/activities/count      - 活动数量")
    print("  /api/snpac/scrape          - 陕西大剧院演出（支持?max=1逐个爬）")
    print("  /api/health                - 健康检查")
    print("  /api/test                  - 测试端点")
    print("=" * 60)
    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)