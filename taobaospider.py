import time
import json
import random
import os
import platform
import pandas as pd
from selenium import webdriver
from selenium.common.exceptions import TimeoutException
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.wait import WebDriverWait
from urllib.parse import quote
from pyquery import PyQuery as pq


class TaobaoSpider:
    def __init__(self):
        options = webdriver.ChromeOptions()
        self.get_user_info()
        if self.is_windows():
            options.binary_location = self.chromepath

        options.add_experimental_option("excludeSwitches", ["enable-automation"])
        options.add_experimental_option("useAutomationExtension", False)
        options.add_experimental_option("prefs", {"prfile.managed_default_content_setting.images": 2})
        self.browser = webdriver.Chrome(options=options, executable_path=self.get_chromedriver_exe_path())

        # 反爬设置  webdriver为 undefined
        self.browser.execute_cdp_cmd("Page.addScriptToEvaluateOnNewDocument", {
            "source": """
        			Object.defineProperty(navigator, 'webdriver', {
        			  get: () => undefined
        			})
        		  """
        })
        self.wait = WebDriverWait(self.browser, 10)
        self.loginurl = "https://login.taobao.com/member/login.jhtml"
        self.trytime = 0
        self.excelfile = "%s.xlsx" % self.keyword

    # 从config.json 文件中读取相关的配置
    def get_user_info(self):
        with open("config.json", "r", encoding="utf-8") as f:
            config = json.load(f)

        self.username = config["username"]
        self.password = config["password"]
        self.keyword = config["keyword"]
        self.maxpage = config["maxpage"]
        self.chromepath = config["chromepath"]
        print(self.password)

    # 判断是否是windows系统
    def is_windows(self):
        return platform.system().lower() == "windows"

    # 获取不同平台的chromedriver的路径
    def get_chromedriver_exe_path(self):
        ret = "./bin/mac/chromedriver"
        if self.is_windows():
            ret = "./bin/win/chromedriver"
        return ret

    def login(self):
        self.browser.get(self.loginurl)
        try:
            # 找到用户名输入框,输入账号密码并登录
            username_input = self.wait.until(EC.presence_of_element_located((By.ID, "fm-login-id")))
            username_input.send_keys(self.username)

            password_input = self.wait.until(EC.presence_of_element_located((By.ID, "fm-login-password")))
            password_input.send_keys(self.password)

            login_button = self.wait.until(EC.presence_of_element_located((By.CLASS_NAME, "fm-button")))
            login_button.click()

            # ”site-nav-login-info-nick” 找到名字标签并打印内容
            taobao_name_tag = self.wait.until(
                EC.presence_of_element_located((By.CLASS_NAME, "site-nav-login-info-nick ")))
            print(f"登录成功:{taobao_name_tag.text}")


        except Exception as e:
            print(e)
            self.browser.close()
            print("登录失败")

    # 爬取相关的内容
    def crawl(self):
        for i in range(1, self.maxpage + 1):
            self.index_page(i)
        self.browser.close()

    # 爬取一页的内容
    def index_page(self, index):
        print("正在爬取第", index, "页")
        try:
            url = "https://s.taobao.com/search?q=" + quote(self.keyword)
            self.browser.get(url)
            # 爬取第二页
            if index > 1:
                input_page = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#mainsrp-pager div.form input.J_Input")))
                submit = self.wait.until(
                    EC.presence_of_element_located((By.CSS_SELECTOR, "#mainsrp-pager div.form span.J_Submit")))
                input_page.clear()
                input_page.send_keys(index)
                submit.click()

            self.wait.until(
                EC.text_to_be_present_in_element((By.CSS_SELECTOR, "#mainsrp-pager li.item.active span"), str(index)))
            self.wait.until(EC.presence_of_element_located((By.CSS_SELECTOR, "#mainsrp-itemlist div.item"), ))
            self.get_product()
            sleep_time = random.randint(1, 10)
            print("主动休眠%d" % (sleep_time))
            time.sleep(sleep_time)
            self.trytime = 0


        except TimeoutException:
            self.trytime += 1
            if self.trytime >= 5:
                if (index < self.maxpage):
                    self.index_page(index + 1)
                    self.trytime = 0

    def get_product(self):
        html = self.browser.page_source
        doc = pq(html)
        items = doc("#mainsrp-itemlist .items .item").items()
        print("-----------"*40 + "\n")
        print(items)
        print("-----------" * 40 + "\n")


        item_list = [item for item in items]

        dfs = []

        for index in range(len(item_list)):
            item = item_list[index]
            product = {
                'image': item.find('.pic .img').attr('data-src'),
                'price': item.find('.price strong').text(),
                'deal': item.find('.deal-cnt').text(),
                'title': item.find('.title').text(),
                'shop': item.find('.shop span').text(),
                'location': item.find('.location').text()
            }
            print(product)
            df = pd.DataFrame(product, index=[1], columns=['image', 'price', 'deal', 'title', 'shop', 'location'])
            dfs.append(df)
        self.save2excel(dfs)

    # 把每页的数据保存到excel中
    def save2excel(self, dfs):
        print('正在将结果保存到excel中')
        total_df = pd.concat(dfs, ignore_index=True)
        if os.path.exists(self.excelfile):
            before_df = pd.read_excel(self.excelfile)
            total_df = pd.concat([before_df, total_df], ignore_index=True).drop_duplicates()
        total_df.to_excel(self.excelfile, sheet_name='淘宝%s情况' % self.keyword, index=False)


if __name__ == "__main__":
    spider = TaobaoSpider()
    spider.login()
    spider.crawl()
