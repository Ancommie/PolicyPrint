import os, time, base64, re
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC

# 屏蔽多余日志
os.environ['TF_CPP_MIN_LOG_LEVEL'] = '2'

# ================= 参数设置 =================
SEARCH_KEYWORDS_LIST = ["生态", "绿色", "低碳", "环保", "碳中和", "碳达峰", "节能减排", "环境保护", "清洁能源"] 
INCLUDE_KEYWORDS = ['决议', '决定', '命令', '公报', '公告', '通告', '意见', '通知', '通报', '报告', '请示', '批复', '议案', '函', '纪要'] 
BASE_PATH = r"E:\政策文件" 
YEARS = range(2013, 2026) 
Sleep_time = 1 
code = ""
sign = ""

# 设定每处理多少个文件就重启一次浏览器（防止内存崩溃）
RESTART_THRESHOLD = 30 
# ===========================================

# 封装启动浏览器的函数
def get_new_driver():
    option = webdriver.EdgeOptions()
    option.add_experimental_option('excludeSwitches', ['enable-logging'])
    option.add_argument('log-level=3')
    option.add_argument('--headless=new') 
    option.add_argument('--disable-gpu')
    option.add_argument('--no-sandbox')
    option.add_argument('--disable-dev-shm-usage') 
    driver = webdriver.Edge(options=option)
    driver.set_page_load_timeout(20) # 全局超时设置
    return driver

# 主体
for year in YEARS:
    print(f"\n========== 开始抓取 {year} 年数据 ==========")
    year_dir = os.path.join(BASE_PATH, str(year))
    os.makedirs(year_dir, exist_ok=True)
    
    # 初始启动浏览器
    driver = get_new_driver()
    
    # 记录当前浏览器实例处理了多少文件
    processed_count_in_session = 0

    try:
        for current_keyword in SEARCH_KEYWORDS_LIST:
            print(f"\n>>> [{year}] 正在搜索关键词：{current_keyword} <<<")
            
            total_found = total_saved = total_skipped = 0
            page_no = 1
            
            while True:
                print(f"[{year}-{current_keyword}] 抓取第 {page_no} 页...")
                
                url = f"https://sousuo.www.gov.cn/sousuo/search.shtml?code={code}&sign={sign}" \
                      f"&searchWord={current_keyword}&dataTypeId=107" \
                      f"&searchBy=all&pageNo={page_no}&orderBy=time&granularity=CUSTOM" \
                      f"&beginDateTime={year}-01-01&endDateTime={year}-12-31"
                
                # 1. 加载列表页
                try:
                    driver.get(url)
                    time.sleep(Sleep_time)
                except Exception as e:
                    if "invalid session id" in str(e).lower():
                        print("  —— [意外] 浏览器崩溃，正在重启...")
                        try: driver.quit()
                        except: pass
                        driver = get_new_driver()
                        processed_count_in_session = 0
                        continue # 重试当前页
                    
                    print("  —— 列表页加载超时，停止加载...")
                    try: driver.execute_script("window.stop();")
                    except: pass

                # 2. 获取链接
                try:
                    WebDriverWait(driver, 10).until(
                        EC.presence_of_element_located((By.XPATH, '//a[contains(@href, "gov.cn")]'))
                    )
                    links = driver.find_elements(By.XPATH, '//a[contains(@href, "gov.cn")]')
                except:
                    links = []

                if not links:
                    print("  —— 本页无结果，切换下一关键词或年份")
                    break

                # 3. 提取有效链接
                link_data = []
                for a in links:
                    try:
                        block_text = a.find_element(By.XPATH, "./../..").text
                        if str(year) not in block_text:
                            continue
                        title = a.text.strip()
                        href = a.get_attribute('href')
                        if title and href:
                            link_data.append((title, href))
                    except:
                        continue

                print(f"找到年份匹配的链接 {len(link_data)} 条")
                total_found += len(link_data)

                # 4. 遍历处理文件
                for title, href in link_data:
                    # 4.1 筛选
                    if not any(k.lower() in title.lower() for k in INCLUDE_KEYWORDS):
                        total_skipped += 1
                        continue
                    
                    # 4.2 去重
                    safe_name = re.sub(r'[\\/*?:"<>|\n\r\t]', '_', title).strip()[:50]
                    out_path = os.path.join(year_dir, f"{safe_name}.pdf")
                    
                    if os.path.exists(out_path):
                        print(f"跳过（文件已存在）：{title}")
                        total_skipped += 1
                        continue

                    print(f"处理：{title}")
                    
                    # 4.3 下载逻辑（带重试）
                    retry_count = 0
                    success = False
                    
                    while retry_count < 2:
                        try:
                            if retry_count == 0:
                                driver.execute_script("window.open('');")
                                driver.switch_to.window(driver.window_handles[1])
                            
                            try:
                                if retry_count > 0:
                                    driver.refresh()
                                else:
                                    driver.get(href)
                            except: pass
                            
                            # 强制停止加载以解决老网页死链问题
                            time.sleep(3) 
                            try: driver.execute_script("window.stop();")
                            except: pass
                            time.sleep(1)

                            pdf_data = driver.execute_cdp_cmd("Page.printToPDF", {
                                "printBackground": True,
                                "paperWidth": 8.27, "paperHeight": 11.69
                            })["data"]
                            
                            with open(out_path, "wb") as f:
                                f.write(base64.b64decode(pdf_data))
                            total_saved += 1
                            processed_count_in_session += 1 # 计数+1
                            success = True
                            break 
                        except Exception as e:
                            print(f"   [失败]: {e}")
                            if "invalid session id" in str(e).lower(): break
                            retry_count += 1
                            time.sleep(2)
                    
                    try: driver.close()
                    except: pass
                    try: driver.switch_to.window(driver.window_handles[0])
                    except: break
                    
                    if not success:
                        print(f"   [放弃] 无法打印")

                # 每处理完一页，检查是不是该重启浏览器了
                if processed_count_in_session >= RESTART_THRESHOLD:
                    print(f"\n>>> 浏览器已处理 {processed_count_in_session} 个文件，正在重启以释放内存... <<<")
                    try:
                        driver.quit()
                    except:
                        pass
                    time.sleep(2) # 歇口气
                    driver = get_new_driver() # 获取新浏览器
                    processed_count_in_session = 0 # 重置计数器
                    print(">>> 浏览器重启完成，继续下一页 \n")

                if len(link_data) < 2:
                    print(f"  —— 数据过少，视为结束")
                    break
                
                page_no += 1
                
            print(f"[{year}-{current_keyword}] 统计：发现 {total_found}, 保存 {total_saved}, 跳过 {total_skipped}")

    finally:
        print(f"========== {year} 年数据抓取完毕 ==========\n")
        try: driver.quit()
        except: pass
