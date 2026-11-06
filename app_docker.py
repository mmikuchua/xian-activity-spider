# app_docker.py - Docker专用API
from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
from spider_docker import run_spider_in_docker
import pandas as pd
import os
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

app = FastAPI(title="西安活动爬虫API (Docker版)")
OUTPUT_DIR = "/tmp/output"
os.makedirs(OUTPUT_DIR, exist_ok=True)


@app.get("/crawl")
async def crawl_activities(background_tasks: BackgroundTasks):
    """Docker环境爬虫接口"""
    try:
        print("🐳 收到Docker爬虫请求...")

        # 在线程池中运行爬虫
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            df = await loop.run_in_executor(pool, run_spider_in_docker)

        if df.empty:
            print("⚠️  返回了空DataFrame，使用模拟数据")
            # 确保始终有数据返回
            test_data = [{
                'title': '保障数据 - Docker测试',
                'time': '2024年保障时间',
                'address': '保障地址',
                'highlights': '保障爬虫流程完整',
                'guide_link': 'https://example.com',
                'source': '保障数据'
            }]
            df = pd.DataFrame(test_data)

        # 生成文件名
        filename = f"xian_activities_{uuid.uuid4().hex[:8]}.xlsx"
        filepath = os.path.join(OUTPUT_DIR, filename)

        # 保存为Excel
        df.to_excel(filepath, index=False, engine='openpyxl')
        print(f"✅ 文件已生成: {filename} ({len(df)} 条数据)")

        # 清理文件
        background_tasks.add_task(os.remove, filepath)

        # 返回文件
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )

    except Exception as e:
        print(f"❌ API错误: {e}")
        raise HTTPException(status_code=500, detail=f"服务器错误: {str(e)}")


@app.get("/")
def home():
    return {"message": "西安活动爬虫API (Docker版) - 访问 /crawl 获取数据"}


@app.get("/health")
def health():
    return {"status": "healthy", "environment": "docker"}