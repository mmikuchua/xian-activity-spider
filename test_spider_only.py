from my_spider import run_xian_spider
import pandas as pd

print("=" * 80)
print("🛠️  开始独立测试爬虫函数")
print("=" * 80)

# 直接调用你的爬虫函数
# test_edge_spider.py
from my_spider import run_xian_spider
import pandas as pd
import sys

print("=" * 80)
print("🌐 Edge浏览器爬虫测试")
print("=" * 80)

print("注意：请确保Microsoft Edge浏览器已安装")
print("如果出现驱动问题，将自动提示下载方式")
print("-" * 80)

try:
    df = run_xian_spider()

    print("\n" + "=" * 80)
    print("📊 测试结果")
    print("=" * 80)

    if not df.empty:
        print(f"✅ 成功！抓取到 {len(df)} 条活动数据")
        print(f"数据形状: {df.shape}")
        print(f"列名: {list(df.columns)}")

        # 保存数据
        output_file = 'edge_spider_output.xlsx'
        df.to_excel(output_file, index=True)
        print(f"💾 数据已保存: {output_file}")

        # 显示数据
        print("\n📋 完整数据:")
        print("-" * 100)
        pd.set_option('display.max_rows', None)
        pd.set_option('display.max_columns', None)
        pd.set_option('display.width', None)
        pd.set_option('display.max_colwidth', 40)
        print(df)
        print("-" * 100)

        sys.exit(0)
    else:
        print("❌ 未能抓取到数据")
        print("\n💡 建议检查:")
        print("1. 查看 debug/edge_page.html 分析页面结构")
        print("2. 确保Edge浏览器正常弹出并显示网页")
        print("3. 确认目标网站可访问")
        sys.exit(1)

except Exception as e:
    print(f"\n❌ 测试过程出错: {e}")
    sys.exit(1)