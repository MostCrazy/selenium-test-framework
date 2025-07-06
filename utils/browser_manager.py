#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
浏览器管理器
提供浏览器驱动的创建、管理和操作功能
"""

import os
import time
from pathlib import Path
from typing import Optional, Dict, Any, List
from datetime import datetime

from selenium import webdriver
from selenium.webdriver.chrome.service import Service as ChromeService
from selenium.webdriver.firefox.service import Service as FirefoxService
from selenium.webdriver.edge.service import Service as EdgeService
from selenium.webdriver.chrome.options import Options as ChromeOptions
from selenium.webdriver.firefox.options import Options as FirefoxOptions
from selenium.webdriver.edge.options import Options as EdgeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import WebDriverException, TimeoutException
from webdriver_manager.chrome import ChromeDriverManager
from webdriver_manager.firefox import GeckoDriverManager
from webdriver_manager.microsoft import EdgeChromiumDriverManager

from .config_manager import BrowserConfig, BrowserType
from .logger_setup import get_logger


class BrowserManager:
    """
    浏览器管理器类
    负责浏览器驱动的创建、配置和管理
    """
    
    def __init__(self, config: BrowserConfig):
        """
        初始化浏览器管理器
        
        Args:
            config: 浏览器配置对象
        """
        self.config = config
        self.logger = get_logger(__name__)
        self.driver: Optional[webdriver.Remote] = None
        self.drivers: List[webdriver.Remote] = []  # 管理多个驱动实例
        
        # 创建截图目录
        self.screenshot_dir = Path("screenshots")
        self.screenshot_dir.mkdir(exist_ok=True)
        
        # 创建下载目录 - 修复属性名
        download_path = config.download_dir if config.download_dir else "downloads"
        self.download_dir = Path(download_path)
        self.download_dir.mkdir(exist_ok=True)

    def _get_chrome_options(self) -> ChromeOptions:
        """获取Chrome选项"""
        options = ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-plugins")
        options.add_argument("--disable-images")
        options.add_argument("--page-load-strategy=eager")
        options.add_argument("--disable-web-security")
        options.add_argument("--allow-running-insecure-content")
        # 新增优化选项
        options.add_argument("--disable-background-timer-throttling")
        options.add_argument("--disable-backgrounding-occluded-windows")
        options.add_argument("--disable-renderer-backgrounding")
        options.add_argument("--disable-features=TranslateUI")
        options.add_argument("--disable-ipc-flooding-protection")
        options.add_argument("--disable-background-networking")
        options.add_argument("--disable-default-apps")
        options.add_argument("--disable-sync")
        options.add_argument("--metrics-recording-only")
        options.add_argument("--no-first-run")
        options.add_argument("--safebrowsing-disable-auto-update")
        options.add_argument("--disable-component-update")
        # 添加基本选项
        if self.config.headless:
            options.add_argument("--headless")
        
        # 添加窗口大小
        if self.config.window_size:
            options.add_argument(f"--window-size={self.config.window_size[0]},{self.config.window_size[1]}")
        
        # 添加Chrome选项
        for option in self.config.get_chrome_options():
            options.add_argument(option)
        
        return options

    def _create_chrome_driver(self):
        """创建Chrome浏览器驱动"""
        try:
            options = self._get_chrome_options()
            
            # 设置下载目录
            prefs = {
                "download.default_directory": str(self.download_dir.absolute()),
                "download.prompt_for_download": False,
                "download.directory_upgrade": True,
                "safebrowsing.enabled": True
            }
            options.add_experimental_option("prefs", prefs)
            
            # 创建服务 - 只创建一次
            try:
                # 优先使用本地ChromeDriver
                service = ChromeService(executable_path="./chromedriver.exe")
            except:
                # 如果本地不存在，则使用ChromeDriverManager下载
                service = ChromeService(ChromeDriverManager().install())
            
            # 创建driver
            driver = webdriver.Chrome(service=service, options=options)
            return driver
            
        except Exception as e:
            self.logger.error(f"创建chrome浏览器驱动失败: {e}")
            raise

    def _create_firefox_driver(self) -> webdriver.Firefox:
        """创建Firefox驱动"""
        options = FirefoxOptions()
        
        # 添加基本选项
        if self.config.headless:
            options.add_argument("--headless")
        
        # 添加Firefox选项
        for option in self.config.get_firefox_options():
            options.add_argument(option)
        
        # 设置下载目录
        options.set_preference("browser.download.folderList", 2)
        options.set_preference("browser.download.dir", str(self.download_dir.absolute()))
        options.set_preference("browser.download.useDownloadDir", True)
        options.set_preference("browser.helperApps.neverAsk.saveToDisk", 
                                 "application/pdf,application/octet-stream,text/csv,application/vnd.ms-excel")
        
        # 创建服务
        service = FirefoxService(GeckoDriverManager().install())
        
        return webdriver.Firefox(service=service, options=options)
    
    def _create_edge_driver(self) -> webdriver.Edge:
        """创建Edge驱动"""
        options = EdgeOptions()
        
        # 添加基本选项
        if self.config.headless:
            options.add_argument("--headless")
        
        # 添加窗口大小
        if self.config.window_size:
            options.add_argument(f"--window-size={self.config.window_size[0]},{self.config.window_size[1]}")
        
        # 设置下载目录
        prefs = {
            "download.default_directory": str(self.download_dir.absolute()),
            "download.prompt_for_download": False,
            "download.directory_upgrade": True,
            "safebrowsing.enabled": True
        }
        options.add_experimental_option("prefs", prefs)
        
        # 创建服务
        service = EdgeService(EdgeChromiumDriverManager().install())
        
        return webdriver.Edge(service=service, options=options)
    
    def _create_safari_driver(self) -> webdriver.Safari:
        """创建Safari驱动"""
        # Safari不支持很多选项，只能创建基本驱动
        return webdriver.Safari()
    
    def _configure_driver(self, driver: webdriver.Remote):
        """
        配置驱动参数
        
        Args:
            driver: WebDriver实例
        """
        # 设置隐式等待
        driver.implicitly_wait(max(self.config.implicit_wait, 15))
        
        # 设置页面加载超时
        driver.set_page_load_timeout(max(self.config.page_load_timeout, 60))
        
        # 设置脚本执行超时
        driver.set_script_timeout(max(self.config.script_timeout, 30))
        
        # 设置窗口大小
        if self.config.window_size and not self.config.headless:
            driver.set_window_size(*self.config.window_size)
        
        # 最大化窗口
        if self.config.maximize_window and not self.config.headless:
            driver.maximize_window()
    
    def get_driver(self, browser_type: Optional[BrowserType] = None) -> webdriver.Remote:
        """
        获取浏览器驱动实例
        
        Args:
            browser_type: 浏览器类型，如果不指定则使用配置中的默认类型
        
        Returns:
            WebDriver实例
        """
        if self.driver is None:
            browser_type = browser_type or self.config.browser_type
            self.driver = self._create_driver(browser_type)
            self.drivers.append(self.driver)
        
        return self.driver
    
    def create_new_driver(self, browser_type: Optional[BrowserType] = None) -> webdriver.Remote:
        """
        创建新的浏览器驱动实例
        
        Args:
            browser_type: 浏览器类型
        
        Returns:
            新的WebDriver实例
        """
        browser_type = browser_type or self.config.browser_type
        new_driver = self._create_driver(browser_type)
        self.drivers.append(new_driver)
        return new_driver
    
    def _create_driver(self, browser_type: BrowserType) -> webdriver.Remote:
        """
        创建浏览器驱动
        
        Args:
            browser_type: 浏览器类型
        
        Returns:
            WebDriver实例
        """
        try:
            if browser_type == BrowserType.CHROME:
                driver = self._create_chrome_driver()
            elif browser_type == BrowserType.FIREFOX:
                driver = self._create_firefox_driver()
            elif browser_type == BrowserType.EDGE:
                driver = self._create_edge_driver()
            elif browser_type == BrowserType.SAFARI:
                driver = self._create_safari_driver()
            else:
                raise ValueError(f"不支持的浏览器类型: {browser_type}")
            
            # 配置驱动
            self._configure_driver(driver)
            
            self.logger.info(f"成功创建{browser_type.value}浏览器驱动")
            return driver
            
        except Exception as e:
            self.logger.error(f"创建{browser_type.value}浏览器驱动失败: {e}")
            raise
    
    def take_screenshot(self, name: str = None) -> str:
        """
        截取屏幕截图
        
        Args:
            name: 截图文件名（不包含扩展名）
        
        Returns:
            截图文件路径
        """
        if not self.driver:
            raise RuntimeError("WebDriver未初始化")
        
        if not name:
            name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        
        screenshot_path = self.screenshot_dir / f"{name}.png"
        
        try:
            self.driver.save_screenshot(str(screenshot_path))
            self.logger.info(f"截图已保存: {screenshot_path}")
            return str(screenshot_path)
        except Exception as e:
            self.logger.error(f"截图失败: {e}")
            raise
    
    def quit_driver(self):
        """关闭当前驱动"""
        if self.driver is not None:
            try:
                self.driver.quit()
                self.logger.info("浏览器驱动已关闭")
            except Exception as e:
                self.logger.error(f"关闭浏览器驱动失败: {e}")
            finally:
                if self.driver in self.drivers:
                    self.drivers.remove(self.driver)
                self.driver = None
    
    def quit_all_drivers(self):
        """关闭所有驱动"""
        for driver in self.drivers[:]:
            try:
                driver.quit()
                self.logger.info("浏览器驱动已关闭")
            except Exception as e:
                self.logger.error(f"关闭浏览器驱动失败: {e}")
        
        self.drivers.clear()
        self.driver = None
    
    def refresh_page(self):
        """刷新当前页面"""
        if self.driver is not None:
            try:
                self.driver.refresh()
                self.logger.info("页面已刷新")
            except Exception as e:
                self.logger.error(f"刷新页面失败: {e}")
    
    def get_current_url(self) -> str:
        """获取当前页面URL"""
        if self.driver is None:
            return ""
        
        try:
            return self.driver.current_url
        except Exception as e:
            self.logger.error(f"获取当前URL失败: {e}")
            return ""
    
    def get_title(self) -> str:
        """获取页面标题"""
        if self.driver is None:
            return ""
        
        try:
            return self.driver.title
        except Exception as e:
            self.logger.error(f"获取页面标题失败: {e}")
            return ""
    
    def switch_to_window(self, window_handle: str):
        """切换到指定窗口"""
        if self.driver is not None:
            try:
                self.driver.switch_to.window(window_handle)
                self.logger.info(f"已切换到窗口: {window_handle}")
            except Exception as e:
                self.logger.error(f"切换窗口失败: {e}")
    
    def get_window_handles(self) -> List[str]:
        """获取所有窗口句柄"""
        if self.driver is None:
            return []
        
        try:
            return self.driver.window_handles
        except Exception as e:
            self.logger.error(f"获取窗口句柄失败: {e}")
            return []
    
    def maximize_window(self):
        """最大化窗口"""
        if self.driver is not None:
            try:
                self.driver.maximize_window()
                self.logger.info("窗口已最大化")
            except Exception as e:
                self.logger.error(f"最大化窗口失败: {e}")
    
    def get_page_source(self) -> str:
        """
        获取页面源码
        
        Returns:
            页面HTML源码
        """
        if self.driver is None:
            return ""
        
        try:
            return self.driver.page_source
        except Exception as e:
            self.logger.error(f"获取页面源码失败: {e}")
            return ""
    
    def execute_script(self, script: str, *args) -> Any:
        """
        执行JavaScript脚本
        
        Args:
            script: JavaScript代码
            *args: 脚本参数
        
        Returns:
            脚本执行结果
        """
        if self.driver is None:
            return None
        
        try:
            return self.driver.execute_script(script, *args)
        except Exception as e:
            self.logger.error(f"执行JavaScript失败: {e}")
            return None
    
    def wait_for_element(self, locator: tuple, timeout: int = 10) -> bool:
        """
        等待元素出现
        
        Args:
            locator: 元素定位器 (By.ID, "element_id")
            timeout: 超时时间（秒）
        
        Returns:
            是否找到元素
        """
        if self.driver is None:
            return False
        
        try:
            wait = WebDriverWait(self.driver, timeout)
            wait.until(EC.presence_of_element_located(locator))
            return True
        except TimeoutException:
            self.logger.warning(f"等待元素超时: {locator}")
            return False
        except Exception as e:
            self.logger.error(f"等待元素失败: {e}")
            return False
    
    def __del__(self):
        """析构函数，确保驱动被正确关闭"""
        self.quit_all_drivers()