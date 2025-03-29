import requests
import random
import logging
import time
from urllib.parse import urlparse
import json
import concurrent.futures

# Configure logging
logging.basicConfig(level=logging.INFO, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# لیست پروکسی‌های پیش‌فرض
DEFAULT_PROXIES = [
    {"host": "104.223.135.178", "port": "10000", "username": "", "password": "", "type": "socks5"},
    {"host": "207.180.202.44", "port": "24722", "username": "", "password": "", "type": "socks5"},
    {"host": "72.206.181.103", "port": "4145", "username": "", "password": "", "type": "socks5"},
    {"host": "103.105.50.194", "port": "8080", "username": "", "password": "", "type": "http"},
    {"host": "198.8.94.170", "port": "4145", "username": "", "password": "", "type": "socks5"}
]

# منابع پروکسی آنلاین
PROXY_SOURCES = {
    'socks5': [
        'https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all',
        'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt',
        'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt',
        'https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt',
    ],
    'socks4': [
        'https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all',
        'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt',
        'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt',
    ],
    'http': [
        'https://api.proxyscrape.com/v2/?request=getproxies&protocol=http&timeout=10000&country=all',
        'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/http.txt',
        'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/http.txt',
        'https://raw.githubusercontent.com/clarketm/proxy-list/master/proxy-list-raw.txt',
    ],
}

# توضیحات و منابع پیشنهادی برای پروکسی
PROXY_RESOURCES_INFO = """
## منابع پیشنهادی برای پروکسی:

1. **سایت‌های ارائه دهنده پروکسی رایگان:**
   - ProxyScrape: https://proxyscrape.com
   - Free-Proxy-List: https://free-proxy-list.net
   - Geonode: https://geonode.com/free-proxy-list
   - Spys.one: https://spys.one

2. **مخازن GitHub با لیست پروکسی:**
   - github.com/TheSpeedX/PROXY-List
   - github.com/ShiftyTR/Proxy-List
   - github.com/hookzof/socks5_list
   - github.com/clarketm/proxy-list

3. **سرویس‌های پروکسی خصوصی (پولی اما مطمئن):**
   - Bright Data (Luminati): https://brightdata.com
   - Oxylabs: https://oxylabs.io
   - SmartProxy: https://smartproxy.com
   - IPRoyal: https://iproyal.com

## انواع پروکسی پشتیبانی شده:
- SOCKS5: بهترین گزینه با پشتیبانی از همه پروتکل‌ها و احراز هویت
- SOCKS4: سریع اما با محدودیت‌های بیشتر نسبت به SOCKS5
- HTTP/HTTPS: مناسب برای وب اما محدودتر از SOCKS

برای هر پروکسی، یک خط جداگانه وارد کنید. فرمت‌های پشتیبانی شده:
- `host:port`
- `protocol://host:port`
- `protocol://username:password@host:port`

مثال:
```
103.105.50.194:8080
socks5://72.206.181.103:4145
http://username:password@1.2.3.4:8080
```
"""

def fetch_proxies_from_source(url, proxy_type):
    """دریافت پروکسی از یک منبع خاص"""
    try:
        response = requests.get(url, timeout=10)
        if response.status_code == 200:
            proxies = []
            for line in response.text.strip().split('\n'):
                line = line.strip()
                if not line or len(line) < 7:  # حداقل طول معتبر (1.1.1.1:1)
                    continue
                    
                try:
                    if ':' in line:
                        # حذف زمان بارگذاری یا توضیحات اضافی
                        line = line.split('#')[0].strip()
                        line = line.split(' ')[0].strip()
                        
                        # تلاش برای پارسینگ host:port
                        host, port = line.split(':')
                        if host and port and len(host.split('.')) == 4:  # بررسی فرمت IP
                            proxies.append({
                                "host": host.strip(),
                                "port": port.strip(),
                                "username": "",
                                "password": "",
                                "type": proxy_type
                            })
                except Exception:
                    continue
                    
            logger.info(f"دریافت {len(proxies)} پروکسی {proxy_type} از {url}")
            return proxies
    except Exception as e:
        logger.warning(f"خطا در دریافت پروکسی‌های {proxy_type} از {url}: {e}")
    
    return []

def get_public_proxies():
    """دریافت لیست پروکسی‌های عمومی از سرویس‌های آنلاین"""
    all_proxies = []
    
    # استفاده از ThreadPoolExecutor برای دریافت موازی پروکسی‌ها
    with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
        future_to_url = {}
        
        # ارسال درخواست‌ها برای همه منابع
        for proxy_type, urls in PROXY_SOURCES.items():
            for url in urls:
                future = executor.submit(fetch_proxies_from_source, url, proxy_type)
                future_to_url[future] = (url, proxy_type)
        
        # دریافت نتایج
        for future in concurrent.futures.as_completed(future_to_url):
            url, proxy_type = future_to_url[future]
            try:
                proxies = future.result()
                all_proxies.extend(proxies)
            except Exception as e:
                logger.error(f"خطا در پردازش نتایج پروکسی از {url}: {e}")
    
    # اگر پروکسی دریافت شد
    if all_proxies:
        logger.info(f"مجموعاً {len(all_proxies)} پروکسی از منابع آنلاین دریافت شد")
        # اختلاط پروکسی‌ها
        random.shuffle(all_proxies)
        # حداکثر 100 پروکسی را برمی‌گردانیم برای جلوگیری از کندی
        return all_proxies[:100]
    
    # اگر نتوانستیم پروکسی دریافت کنیم، از لیست پیش‌فرض استفاده می‌کنیم
    logger.info(f"استفاده از {len(DEFAULT_PROXIES)} پروکسی پیش‌فرض")
    return DEFAULT_PROXIES

def parse_custom_proxy(proxy_string):
    """تبدیل رشته پروکسی به دیکشنری پروکسی"""
    try:
        # اگر پروکسی با فرمت URL باشد (مثل socks5://user:pass@host:port)
        if '://' in proxy_string:
            parsed = urlparse(proxy_string)
            
            # استخراج نوع پروکسی
            proxy_type = parsed.scheme
            
            # استخراج نام کاربری و رمز عبور
            username = ""
            password = ""
            if '@' in parsed.netloc:
                auth, address = parsed.netloc.split('@')
                if ':' in auth:
                    username, password = auth.split(':')
            else:
                address = parsed.netloc
            
            # استخراج هاست و پورت
            host, port = address.split(':')
            
            return {
                "host": host,
                "port": port,
                "username": username,
                "password": password,
                "type": proxy_type
            }
            
        # اگر پروکسی با فرمت ساده باشد (مثل host:port)
        elif ':' in proxy_string:
            host, port = proxy_string.split(':')
            return {
                "host": host.strip(),
                "port": port.strip(),
                "username": "",
                "password": "",
                "type": "socks5"  # نوع پیش‌فرض
            }
    except Exception as e:
        logger.error(f"خطا در تبدیل رشته پروکسی: {e}")
    
    return None

def format_proxy_for_requests(proxy_data):
    """تبدیل دیکشنری پروکسی به فرمت مناسب برای کتابخانه requests"""
    if not proxy_data:
        return None
    
    proxy_type = proxy_data.get("type", "socks5").lower()
    host = proxy_data.get("host", "")
    port = proxy_data.get("port", "")
    username = proxy_data.get("username", "")
    password = proxy_data.get("password", "")
    
    # ساخت URL پروکسی
    if username and password:
        proxy_url = f"{proxy_type}://{username}:{password}@{host}:{port}"
    else:
        proxy_url = f"{proxy_type}://{host}:{port}"
    
    if proxy_type in ["http", "https"]:
        return {"http": proxy_url, "https": proxy_url}
    elif proxy_type in ["socks4", "socks5"]:
        return {"http": proxy_url, "https": proxy_url}
    else:
        logger.warning(f"نوع پروکسی نامعتبر: {proxy_type}")
        return None

def test_proxy(proxy_data, timeout=5):
    """تست کارکرد پروکسی"""
    formatted_proxy = format_proxy_for_requests(proxy_data)
    if not formatted_proxy:
        return False
    
    try:
        logger.info(f"تست پروکسی: {proxy_data.get('host')}:{proxy_data.get('port')}")
        start_time = time.time()
        response = requests.get("https://httpbin.org/ip", 
                               proxies=formatted_proxy, 
                               timeout=timeout)
        elapsed = time.time() - start_time
        
        if response.status_code == 200:
            logger.info(f"پروکسی کار می‌کند. زمان پاسخ: {elapsed:.2f} ثانیه")
            return True
        else:
            logger.warning(f"پروکسی کار نمی‌کند. کد وضعیت: {response.status_code}")
            return False
    except Exception as e:
        logger.warning(f"خطا در تست پروکسی: {e}")
        return False

def get_working_proxy():
    """یافتن یک پروکسی کارآمد از لیست پروکسی‌ها"""
    # ابتدا لیست پروکسی‌های عمومی را دریافت می‌کنیم
    proxies = get_public_proxies()
    
    # تست تصادفی حداکثر 5 پروکسی
    random.shuffle(proxies)
    for proxy in proxies[:5]:
        if test_proxy(proxy):
            return proxy
    
    # اگر پروکسی کارآمدی پیدا نشد، از لیست پیش‌فرض استفاده می‌کنیم
    logger.warning("هیچ پروکسی کارآمدی پیدا نشد. استفاده از لیست پیش‌فرض")
    for proxy in DEFAULT_PROXIES:
        if test_proxy(proxy):
            return proxy
    
    # اگر هیچ پروکسی کارآمدی پیدا نشد، بدون پروکسی ادامه می‌دهیم
    logger.error("هیچ پروکسی کارآمدی پیدا نشد!")
    return None

def parse_proxy_list(proxy_list_text):
    """
    تبدیل لیست پروکسی‌ها از متن به لیستی از دیکشنری‌های پروکسی
    
    Args:
        proxy_list_text: متن حاوی لیست پروکسی‌ها (هر پروکسی در یک خط)
        
    Returns:
        list: لیست دیکشنری‌های پروکسی
    """
    proxy_list = []
    for line in proxy_list_text.strip().split('\n'):
        line = line.strip()
        if not line:
            continue
            
        proxy = parse_custom_proxy(line)
        if proxy:
            proxy_list.append(proxy)
            
    logger.info(f"تعداد {len(proxy_list)} پروکسی از لیست وارد شده پردازش شد")
    return proxy_list

def find_working_proxy_from_list(proxy_list):
    """
    یافتن اولین پروکسی کارآمد از لیست پروکسی‌ها
    
    Args:
        proxy_list: لیست دیکشنری‌های پروکسی
        
    Returns:
        dict: اولین پروکسی کارآمد یا None اگر هیچ پروکسی کارآمدی پیدا نشد
    """
    if not proxy_list:
        logger.warning("لیست پروکسی خالی است")
        return None
        
    for i, proxy in enumerate(proxy_list):
        logger.info(f"تست پروکسی {i+1} از {len(proxy_list)}: {proxy.get('host')}:{proxy.get('port')}")
        if test_proxy(proxy):
            logger.info(f"پروکسی کارآمد پیدا شد: {proxy.get('host')}:{proxy.get('port')}")
            return proxy
            
    logger.warning("هیچ پروکسی کارآمدی در لیست پیدا نشد")
    return None

def get_proxy(custom_proxy=None):
    """
    دریافت یک پروکسی برای استفاده در برنامه
    
    Args:
        custom_proxy: رشته پروکسی سفارشی (اختیاری)
        
    Returns:
        dict: دیکشنری پروکسی یا None اگر پروکسی موجود نباشد
    """
    # اگر پروکسی سفارشی ارائه شده باشد، آن را پردازش می‌کنیم
    if custom_proxy:
        # بررسی اینکه آیا لیستی از پروکسی‌ها است یا یک پروکسی تکی
        if '\n' in custom_proxy:
            # پردازش لیست پروکسی‌ها
            proxy_list = parse_proxy_list(custom_proxy)
            working_proxy = find_working_proxy_from_list(proxy_list)
            if working_proxy:
                return working_proxy
            logger.warning("هیچ پروکسی کارآمدی در لیست سفارشی پیدا نشد")
        else:
            # پردازش یک پروکسی تکی
            proxy = parse_custom_proxy(custom_proxy)
            if proxy and test_proxy(proxy):
                logger.info(f"استفاده از پروکسی سفارشی: {proxy.get('host')}:{proxy.get('port')}")
                return proxy
            else:
                logger.warning("پروکسی سفارشی کار نمی‌کند")
    
    # در غیر این صورت، یک پروکسی کارآمد پیدا می‌کنیم
    return get_working_proxy()

# تابع برای تبدیل پروکسی به فرمت مورد نیاز Selenium
def get_proxy_for_selenium(proxy_data):
    """تبدیل دیکشنری پروکسی به فرمت مناسب برای Selenium"""
    if not proxy_data:
        return None
    
    proxy_type = proxy_data.get("type", "socks5").lower()
    host = proxy_data.get("host", "")
    port = proxy_data.get("port", "")
    username = proxy_data.get("username", "")
    password = proxy_data.get("password", "")
    
    # تنظیمات پروکسی برای Selenium
    proxy_settings = {
        "proxyType": proxy_type.upper(),
    }
    
    if proxy_type in ["http", "https"]:
        proxy_settings["httpProxy"] = f"{host}:{port}"
        proxy_settings["sslProxy"] = f"{host}:{port}"
    elif proxy_type == "socks5":
        proxy_settings["socksProxy"] = f"{host}:{port}"
        proxy_settings["socksVersion"] = 5
    elif proxy_type == "socks4":
        proxy_settings["socksProxy"] = f"{host}:{port}"
        proxy_settings["socksVersion"] = 4
    
    if username and password:
        proxy_settings["socksUsername"] = username
        proxy_settings["socksPassword"] = password
    
    return proxy_settings