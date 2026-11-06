from flask import Flask, jsonify, request
from flask_cors import CORS
import threading
import json
import time
import os
import sys
import traceback
import pandas as pd
from datetime import datetime

# 将原始爬虫代码导入
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.chrome.service import Service
from selenium.common.exceptions import TimeoutException, NoSuchElementException
from webdriver_manager.chrome import ChromeDriverManager
from bs4 import BeautifulSoup
import pandas as pd

# 创建Flask应用
app = Flask(__name__)
CORS(app)  # 允许跨域请求


# ================= 爬虫函数（基于您的代码） =================
def scrape_activities(save_to_file=False):
    """
    爬取活动数据的主函数
    :param save_to_file: 是否保存到文件
    :return: 爬取的数据字典
    """
    print("🚀 开始爬取活动数据...")

    # 配置部分
    TARGET_URL = 'https://xa.bendibao.com/xiuxian/huodongrili/'

    TABLE_HEADERS = {
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

    try:
        # 1. 启动浏览器
        print("1. 正在启动浏览器...")
        options = webdriver.ChromeOptions()
        options.add_argument('--headless')  # 无头模式，后台运行
        options.add_argument('--disable-gpu')
        options.add_argument('--no-sandbox')
        options.add_argument('--disable-dev-shm-usage')
        options.add_argument('--remote-debugging-port=9222')
        options.add_argument('--disable-blink-features=AutomationControlled')
        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option('useAutomationExtension', False)

        # 使用webdriver-manager自动管理驱动
        service = Service()
        driver = webdriver.Chrome(service=service, options=options)
        driver.execute_script("Object.defineProperty(navigator, 'webdriver', {get: () => undefined})")
        driver.implicitly_wait(10)

        # 2. 访问页面
        print(f"2. 访问页面: {TARGET_URL}")
        driver.get(TARGET_URL)

        # 3. 确保页面加载
        print("3. 等待页面初始化...")
        wait = WebDriverWait(driver, 15)
        wait.until(EC.presence_of_element_located((By.CLASS_NAME, "main-block-single")))

        # 4. 模拟点击"展开更多"按钮
        print("4. 开始加载完整数据 (模拟点击'展开更多')...")
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
            result['status'] = 'warning'
            result['message'] = '未找到任何活动信息'
            return result

        # 7. 提取每个活动的详细信息
        all_activities_data = []

        for idx, container in enumerate(activity_containers, 1):
            activity = {'index': idx}

            # 提取活动名称
            title_elem = container.find(class_='main-single-block-titles')
            activity['title'] = title_elem.get_text(strip=True) if title_elem else '未获取'

            # 提取活动时间
            time_elem = container.find(class_='time-dia-hover')
            activity['time'] = time_elem.get_text(strip=True) if time_elem else '未获取'

            # 提取活动地址
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

            # 提取活动亮点
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
            activity['id'] = f"act_{idx}_{int(time.time())}"

            all_activities_data.append(activity)

        # 8. 转换为DataFrame
        df = pd.DataFrame(all_activities_data)

        # 重命名列
        rename_dict = {key: TABLE_HEADERS.get(key, key) for key in df.columns if key not in ['index', 'id']}
        df.rename(columns=rename_dict, inplace=True)

        # 9. 如果保存到文件
        if save_to_file:
            timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
            csv_filename = f'西安本地宝活动_{timestamp}.csv'
            df.to_csv(csv_filename, encoding='utf-8-sig', index=False)
            print(f"✅ 数据已保存为 CSV 文件: {csv_filename}")

            # 保存JSON文件
            json_filename = f'西安本地宝活动_{timestamp}.json'
            with open(json_filename, 'w', encoding='utf-8') as f:
                json.dump(all_activities_data, f, ensure_ascii=False, indent=2)
            print(f"✅ 数据已保存为 JSON 文件: {json_filename}")

        # 更新结果
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


# ================= API路由 =================
@app.route('/')
def home():
    """API首页"""
    return jsonify({
        'service': '西安本地宝活动爬虫API',
        'version': '1.0.0',
        'endpoints': {
            '/api/activities': '获取所有活动数据',
            '/api/activities/latest': '获取最新爬取的数据',
            '/api/activities/count': '获取活动数量',
            '/api/health': '健康检查'
        },
        'usage': '发送GET请求到相应端点获取数据'
    })


@app.route('/api/activities', methods=['GET'])
def get_activities():
    """爬取并返回所有活动数据"""
    try:
        # 获取查询参数
        save_file = request.args.get('save', 'false').lower() == 'true'
        limit = request.args.get('limit', type=int)

        # 执行爬虫
        print(f"接收到爬虫请求，save_file={save_file}")
        result = scrape_activities(save_to_file=save_file)

        # 如果指定了limit，限制返回数据量
        if limit and result['status'] == 'success':
            result['data'] = result['data'][:limit]
            result['metadata']['returned_count'] = len(result['data'])

        return jsonify(result), 200 if result['status'] != 'error' else 500

    except Exception as e:
        return jsonify({
            'status': 'error',
            'message': f'API处理错误: {str(e)}',
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 500


@app.route('/api/activities/latest', methods=['GET'])
def get_latest_activities():
    """获取最新活动（模拟缓存，实际每次都是实时爬取）"""
    try:
        limit = request.args.get('limit', 10, type=int)
        result = scrape_activities(save_to_file=False)

        if result['status'] == 'success':
            # 只返回最新的几个活动
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
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 500


@app.route('/api/activities/count', methods=['GET'])
def get_activities_count():
    """获取活动数量"""
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
        return jsonify({
            'status': 'error',
            'message': str(e),
            'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
        }), 500


@app.route('/api/health', methods=['GET'])
def health_check():
    """健康检查端点"""
    return jsonify({
        'status': 'healthy',
        'service': 'activity-scraper-api',
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S'),
        'uptime': 'running'
    }), 200


@app.route('/api/test', methods=['GET'])
def test_endpoint():
    """测试端点，快速返回"""
    return jsonify({
        'status': 'success',
        'message': 'API服务正常运行',
        'test_data': [
            {
                'id': 'test_001',
                'title': '测试活动 - 音乐节',
                'time': '2024-01-01 19:00',
                'address': '西安大唐不夜城',
                'highlights': '知名乐队现场演出',
                'guide_link': 'https://example.com/guide',
                'source': '测试数据'
            }
        ],
        'timestamp': datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    }), 200


# ================= 启动应用 =================
if __name__ == '__main__':
    port = int(os.environ.get('PORT', 5000))

    print("=" * 60)
    print("🚀 西安本地宝活动爬虫API服务")
    print(f"📡 服务启动在: http://localhost:{port}")
    print("=" * 60)
    print("可用端点:")
    print("  /              - 服务首页")
    print("  /api/activities - 获取所有活动数据")
    print("  /api/health    - 健康检查")
    print("  /api/test      - 测试端点")
    print("=" * 60)

    app.run(host='0.0.0.0', port=port, debug=False, threaded=True)