from fastapi import FastAPI, BackgroundTasks, HTTPException
from fastapi.responses import FileResponse
import pandas as pd
import os
import uuid
import asyncio
from concurrent.futures import ThreadPoolExecutor

# 导入你的爬虫函数（我们稍后会创建它）
from my_spider import run_xian_spider

app = FastAPI(title="西安活动爬虫API")
OUTPUT_DIR = "./output"
os.makedirs(OUTPUT_DIR, exist_ok=True)

@app.get("/crawl")
async def crawl_activities(background_tasks: BackgroundTasks):
    """API接口：触发爬虫并返回Excel文件"""
    try:
        print("🧠 收到请求，开始执行爬虫...")
        # 在线程池中运行爬虫
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor() as pool:
            df = await loop.run_in_executor(pool, run_xian_spider)

        if df.empty:
            raise HTTPException(status_code=500, detail="未抓取到数据")

        # 保存为Excel文件
        filename = f"xian_活动_{uuid.uuid4().hex[:8]}.xlsx"
        filepath = os.path.join(OUTPUT_DIR, filename)
        df.to_excel(filepath, index=True, engine='openpyxl')
        print(f"📁 文件已生成: {filepath}")

        # 设置返回后自动清理临时文件
        background_tasks.add_task(os.remove, filepath)

        # 以文件流形式返回
        return FileResponse(
            path=filepath,
            filename=filename,
            media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        )
    except Exception as e:
        print(f"❌ API处理失败: {e}")
        raise HTTPException(status_code=500, detail=f"服务器内部错误: {str(e)}")

if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="127.0.0.1", port=8000)