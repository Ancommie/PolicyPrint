import os, time, base64, re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC


# 屏蔽多余日志
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# 配置驱动器
option = webdriver.EdgeOptions()
option.add_experimental_option('excludeSwitches', ['enable-logging'])
option.add_argument('log-level=3')
option.add_argument('--headless')
driver = webdriver.Edge(options=option)


# 参数设置(关键词、保存路径、爬取年份)
keyword = "可持续" # 主题(全文搜索包含其的公文并按相关性排序)
INCLUDE_KEYWORDS = ['决议', '决定', '命令', '公报', '公告', '通告', '意见', '通知', '通报', '报告', '请示', '批复', '议案', '函', '纪要']  # 文章标题包含的关键词(文种等)
BASE_PATH = r"D:\\大创\\文档\\政策文件\\" # 存储路径
YEARS = range(2018, 2024) # 爬取年份范围
Sleep_time = 1 # 设定间隔时长、防止封ip
# 自行访问https://sousuo.www.gov.cn，进行检索，找到下面的code和sign参数
code = ""
sign = ""


# 主体
for year in YEARS:
    total_found = total_saved = total_skipped = 0
    year_dir = os.path.join(BASE_PATH, str(year))
    os.makedirs(year_dir, exist_ok=True)

    page_no = 1
    while True:
        print(f"[{year}] 抓取第 {page_no} 页...")
        url = f"https://sousuo.www.gov.cn/sousuo/search.shtml?code={code}&sign={sign}" \
              f"&searchWord={keyword}&dataTypeId=107" \
              f"&searchBy=all&pageNo={page_no}&orderBy=related&granularity=CUSTOM" \
              f"&beginDateTime={year}-01-01&endDateTime={year}-12-31"
        
        driver.get(url)
        time.sleep(Sleep_time)

        # 立即获取并缓存链接数据
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, '//a[contains(@href, "gov.cn")]'))
            )
            links = driver.find_elements(By.XPATH, '//a[contains(@href, "gov.cn")]')
        except:
            links = []

        if not links:
            print("  —— 本页无结果，终止抓取")
            break

        # 提前提取所有链接信息
        link_data = []
        for a in links:
            try:
                title = a.text.strip()
                href = a.get_attribute('href')
                if title and href:
                    link_data.append((title, href))
            except:
                continue

        print(f"找到有效链接 {len(link_data)} 条")
        total_found += len(link_data)

        for title, href in link_data:
            # 仅保留含有关键词的条目
            if not any(k.lower() in title.lower() for k in INCLUDE_KEYWORDS):
                total_skipped += 1
                print(f"跳过（不含关键词）：{title}")
                continue

            print(f"处理：{title}")
            try:
                # 新标签页打开防止页面状态丢失
                driver.execute_script("window.open('');")
                driver.switch_to.window(driver.window_handles[1])
                driver.get(href)
                time.sleep(Sleep_time)
                
                # 生成PDF
                pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {"printBackground": True})["data"]
                pdf = base64.b64decode(pdf_data)
                
                # 关闭当前标签页并切换回原页面
                driver.close()
                driver.switch_to.window(driver.window_handles[0])
            except Exception as e:
                print(f"处理失败：{e}")
                driver.switch_to.window(driver.window_handles[0])
                continue

            # 保存文件
            safe_name = re.sub(r'[\\/*?:"<>|]', '_', title)[:50]
            out_path = os.path.join(year_dir, f"{safe_name}.pdf")
            try:
                with open(out_path, "wb") as f:
                    f.write(pdf)
                total_saved += 1
            except Exception as e:
                print(f"保存失败：{e}")

        
        # 页码上限保护
        # if page_no >= 500:
        if len(link_data) < 10:
            print(f"达到页码限制/已完成爬取，程序终止")
            break
        
        page_no += 1
        
    print(f"[{year}] 完成：共发现 {total_found} 条，保存 {total_saved} 个，跳过 {total_skipped} 条\n")

driver.quit()