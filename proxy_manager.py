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
        # API جدید از ProxyScrape
        'https://api.proxyscrape.com/v4/free-proxy-list/get?request=display_proxies&proxy_format=protocol|port&format=text',
        'https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&protocol=socks5&timeout=10000&country=all&ssl=all&anonymity=all',
        # APIهای قبلی
        'https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks5&timeout=10000&country=all',
        'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks5.txt',
        'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks5.txt',
        'https://raw.githubusercontent.com/hookzof/socks5_list/master/proxy.txt',
    ],
    'socks4': [
        # API جدید از ProxyScrape
        'https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&protocol=socks4&timeout=10000&country=all&ssl=all&anonymity=all',
        # APIهای قبلی
        'https://api.proxyscrape.com/v2/?request=getproxies&protocol=socks4&timeout=10000&country=all',
        'https://raw.githubusercontent.com/TheSpeedX/PROXY-List/master/socks4.txt',
        'https://raw.githubusercontent.com/ShiftyTR/Proxy-List/master/socks4.txt',
    ],
    'http': [
        # API جدید از ProxyScrape
        'https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&protocol=http&timeout=10000&country=all&ssl=all&anonymity=all',
        # APIهای قبلی
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

def test_proxy(proxy_data, timeout=3):
    """
    تست کارکرد پروکسی با تایم‌اوت کوتاه‌تر و مدیریت خطای بهتر
    
    Args:
        proxy_data: دیکشنری اطلاعات پروکسی
        timeout: زمان انتظار به ثانیه (کوتاه‌تر برای جلوگیری از کرش)
        
    Returns:
        bool: نتیجه تست پروکسی (True اگر کار می‌کند)
    """
    formatted_proxy = format_proxy_for_requests(proxy_data)
    if not formatted_proxy:
        return False
    
    # بررسی ورودی برای جلوگیری از خطاهای عجیب
    host = proxy_data.get('host', '')
    port = proxy_data.get('port', '')
    if not host or not port:
        logger.warning(f"پروکسی نامعتبر (host یا port خالی است): {proxy_data}")
        return False
        
    try:
        logger.info(f"تست پروکسی: {host}:{port}")
        
        # استفاده از سایت ساده‌تر برای تست سریع‌تر
        test_url = "http://httpbin.org/status/200"
        
        # تایم‌اوت کوتاه برای جلوگیری از معطلی طولانی
        start_time = time.time()
        
        # درخواست با کنترل خطای بیشتر
        try:
            response = requests.get(
                test_url, 
                proxies=formatted_proxy, 
                timeout=timeout,
                stream=True,  # برای جلوگیری از دانلود کامل محتوا
                verify=False,  # برای جلوگیری از مشکلات SSL
                allow_redirects=False  # برای جلوگیری از ریدایرکت‌های طولانی
            )
            
            # فقط هدر را بررسی می‌کنیم، نه محتوا
            resp_code = response.status_code
            response.close()  # بستن اتصال به سرعت
            
            elapsed = time.time() - start_time
            
            if resp_code < 400:  # هر کد موفقیت یا ریدایرکت قابل قبول است
                logger.info(f"پروکسی کار می‌کند. زمان پاسخ: {elapsed:.2f} ثانیه")
                return True
            else:
                logger.warning(f"پروکسی خطا برگرداند. کد وضعیت: {resp_code}")
                return False
                
        except requests.exceptions.ConnectTimeout:
            logger.warning(f"تایم‌اوت اتصال به پروکسی {host}:{port}")
            return False
        except requests.exceptions.ReadTimeout:
            logger.warning(f"تایم‌اوت خواندن از پروکسی {host}:{port}")
            return False
        except requests.exceptions.ProxyError:
            logger.warning(f"خطای پروکسی برای {host}:{port}")
            return False
        except requests.exceptions.SSLError:
            logger.warning(f"خطای SSL برای پروکسی {host}:{port}")
            return False
        except Exception as req_e:
            logger.warning(f"خطای درخواست: {req_e}")
            return False
            
    except Exception as e:
        logger.warning(f"خطای نامشخص در تست پروکسی: {e}")
        return False

def get_proxyscrape_proxies(api_url=None):
    """
    دریافت پروکسی از سرویس ProxyScrape با استفاده از API جدید
    
    Args:
        api_url: آدرس API برای دریافت پروکسی (اختیاری)
        
    Returns:
        list: لیست پروکسی‌های دریافت شده
    """
    # اگر آدرس API ارائه نشده باشد، از آدرس پیش‌فرض استفاده می‌کنیم
    if not api_url:
        api_url = 'https://api.proxyscrape.com/v4/free-proxy-list/get?request=displayproxies&protocol=all&timeout=10000&country=all&ssl=all&anonymity=all'
    
    logger.info(f"دریافت پروکسی از ProxyScrape API: {api_url}")
    
    try:
        response = requests.get(api_url, timeout=10)
        if response.status_code == 200:
            proxies = []
            for line in response.text.strip().split('\n'):
                line = line.strip()
                if not line or len(line) < 7:  # حداقل طول معتبر (1.1.1.1:1)
                    continue
                
                try:
                    # اگر با پروتکل شروع می‌شود (socks5://ip:port)
                    if line.startswith(('http://', 'https://', 'socks4://', 'socks5://')):
                        proxy = parse_custom_proxy(line)
                        if proxy:
                            proxies.append(proxy)
                    
                    # فرمت ساده ip:port
                    elif ':' in line:
                        host, port = line.split(':')
                        # سعی می‌کنیم نوع پروکسی را از URL تشخیص دهیم
                        if 'protocol=socks5' in api_url:
                            proxy_type = 'socks5'
                        elif 'protocol=socks4' in api_url:
                            proxy_type = 'socks4'
                        elif 'protocol=http' in api_url:
                            proxy_type = 'http'
                        else:
                            # اگر نتوانیم نوع را تشخیص دهیم، socks5 را فرض می‌کنیم
                            proxy_type = 'socks5'
                            
                        proxies.append({
                            "host": host.strip(),
                            "port": port.strip(),
                            "username": "",
                            "password": "",
                            "type": proxy_type
                        })
                except Exception as e:
                    logger.debug(f"خطا در پردازش خط پروکسی: {e}")
                    continue
                    
            logger.info(f"تعداد {len(proxies)} پروکسی از ProxyScrape API دریافت شد")
            return proxies
        else:
            logger.warning(f"خطا در دریافت پروکسی از ProxyScrape API. کد پاسخ: {response.status_code}")
    except Exception as e:
        logger.warning(f"خطا در دریافت پروکسی از ProxyScrape API: {e}")
    
    return []

def get_working_proxy():
    """یافتن یک پروکسی کارآمد از لیست پروکسی‌ها"""
    # ابتدا از API جدید ProxyScrape استفاده می‌کنیم
    proxies = get_proxyscrape_proxies()
    
    # تست پروکسی‌های دریافت شده از API جدید
    for proxy in proxies[:10]:  # حداکثر 10 پروکسی را تست می‌کنیم
        if test_proxy(proxy):
            logger.info(f"پروکسی کارآمد از ProxyScrape API پیدا شد: {proxy.get('host')}:{proxy.get('port')}")
            return proxy
    
    # اگر پروکسی کارآمدی از API جدید پیدا نشد، از سایر منابع استفاده می‌کنیم
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

def read_proxy_file(file_path):
    """
    خواندن فایل حاوی لیست پروکسی‌ها
    
    Args:
        file_path: مسیر فایل حاوی پروکسی‌ها (هر پروکسی در یک خط)
        
    Returns:
        list: لیست دیکشنری‌های پروکسی
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            proxy_text = f.read()
        return parse_proxy_list(proxy_text)
    except Exception as e:
        logger.error(f"خطا در خواندن فایل پروکسی: {e}")
        return []

def save_temp_proxy_file(proxy_text, user_id):
    """
    ذخیره موقت متن پروکسی در فایل
    
    Args:
        proxy_text: متن حاوی لیست پروکسی‌ها
        user_id: شناسه کاربر برای ایجاد فایل مختص کاربر
        
    Returns:
        str: مسیر فایل ذخیره شده
    """
    try:
        file_path = f"/tmp/proxies_{user_id}.txt"
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(proxy_text)
        return file_path
    except Exception as e:
        logger.error(f"خطا در ذخیره فایل موقت پروکسی: {e}")
        return None

def find_multiple_working_proxies(proxy_list, count=1, timeout=3, max_workers=3):
    """
    یافتن چندین پروکسی کارآمد از لیست پروکسی‌ها با استفاده از اجرای همزمان
    با محدودیت‌های سختگیرانه برای جلوگیری از کرش شدن
    
    Args:
        proxy_list: لیست دیکشنری‌های پروکسی
        count: تعداد پروکسی‌های کارآمد مورد نیاز
        timeout: زمان انتظار برای تست هر پروکسی (ثانیه)
        max_workers: حداکثر تعداد تردهای همزمان برای تست پروکسی‌ها
        
    Returns:
        list: لیست پروکسی‌های کارآمد
    """
    if not proxy_list:
        logger.warning("لیست پروکسی خالی است!")
        return []
        
    # محدود کردن تعداد پروکسی‌ها به 50 تا برای حفاظت از سرور
    limited_proxy_list = proxy_list[:50]
    logger.info(f"تست {len(limited_proxy_list)} پروکسی (از مجموع {len(proxy_list)}) برای یافتن {count} پروکسی کارآمد...")
    working_proxies = []
    
    # روش امن‌تر: ابتدا تست ترتیبی تا پیدا کردن اولین پروکسی سالم
    for i, proxy in enumerate(limited_proxy_list[:10]):
        try:
            logger.info(f"تست ترتیبی پروکسی {i+1}/10: {proxy.get('host')}:{proxy.get('port')}")
            is_working = test_proxy(proxy, timeout)
            if is_working:
                logger.info(f"پروکسی کارآمد یافت شد: {proxy.get('host')}:{proxy.get('port')}")
                working_proxies.append(proxy)
                if len(working_proxies) >= count:
                    return working_proxies
        except Exception as e:
            logger.error(f"خطا در تست پروکسی {proxy.get('host')}:{proxy.get('port')}: {e}")
        
        # اضافه کردن تاخیر کوتاه بین درخواست‌ها برای جلوگیری از فشار بیش از حد
        time.sleep(0.2)
    
    # اگر هنوز به تعداد کافی نرسیده‌ایم، از روش موازی با محدودیت استفاده می‌کنیم
    if len(working_proxies) < count and limited_proxy_list[10:]:
        try:
            remaining_proxies = limited_proxy_list[10:]
            logger.info(f"تست موازی {len(remaining_proxies)} پروکسی باقیمانده با {max_workers} کارگر همزمان...")
            
            # تقسیم باقیمانده پروکسی‌ها به گروه‌های کوچک برای جلوگیری از کرش
            batch_size = 10
            remaining_count = count - len(working_proxies)
            
            for i in range(0, len(remaining_proxies), batch_size):
                batch = remaining_proxies[i:i+batch_size]
                
                logger.info(f"پردازش گروه {i//batch_size + 1} با {len(batch)} پروکسی...")
                
                # برای تست همزمان پروکسی‌ها از ThreadPoolExecutor استفاده می‌کنیم
                with concurrent.futures.ThreadPoolExecutor(max_workers=max_workers) as executor:
                    future_to_proxy = {executor.submit(test_proxy, proxy, timeout): proxy for proxy in batch}
                    
                    for future in concurrent.futures.as_completed(future_to_proxy):
                        proxy = future_to_proxy[future]
                        try:
                            is_working = future.result()
                            if is_working:
                                logger.info(f"پروکسی کارآمد یافت شد: {proxy.get('host')}:{proxy.get('port')}")
                                working_proxies.append(proxy)
                                
                                # اگر به تعداد مورد نیاز رسیدیم، خروج از حلقه
                                if len(working_proxies) >= count:
                                    break
                        except Exception as e:
                            logger.error(f"خطا در تست پروکسی {proxy.get('host')}:{proxy.get('port')}: {e}")
                
                # اگر به تعداد مورد نیاز رسیدیم، خروج از حلقه اصلی
                if len(working_proxies) >= count:
                    break
                
                # اضافه کردن تاخیر بین دسته‌ها
                time.sleep(0.5)
                
        except Exception as e:
            logger.error(f"خطا در تست موازی پروکسی‌ها: {e}")
    
    logger.info(f"{len(working_proxies)} پروکسی کارآمد از {len(limited_proxy_list)} پروکسی پیدا شد.")
    return working_proxies

def get_proxy_from_api_url(api_url):
    """
    دریافت پروکسی از یک URL API خارجی با مدیریت خطای بهتر و محدودیت‌های سختگیرانه
    
    Args:
        api_url: آدرس API برای دریافت پروکسی
        
    Returns:
        dict: یک پروکسی کارآمد یا None اگر پروکسی کارآمدی پیدا نشد
    """
    logger.info(f"دریافت پروکسی از URL API خارجی: {api_url}")
    
    try:
        # بررسی اعتبار URL
        if not api_url.startswith(('http://', 'https://')):
            logger.warning(f"URL نامعتبر: {api_url}")
            return None
            
        # تنظیم تایم‌اوت و تعداد تلاش مجدد
        max_retries = 2
        request_timeout = 5
        
        # تلاش برای دریافت پروکسی‌ها با تعداد محدود تلاش مجدد
        for attempt in range(max_retries):
            try:
                logger.info(f"تلاش {attempt+1}/{max_retries} برای دریافت پروکسی از API...")
                
                # ابتدا دریافت لیست پروکسی‌ها
                proxies = get_proxyscrape_proxies(api_url)
                
                # اگر پروکسی دریافت نشد
                if not proxies:
                    logger.warning(f"هیچ پروکسی از {api_url} دریافت نشد")
                    time.sleep(1)  # تاخیر قبل از تلاش مجدد
                    continue
                
                # تست پروکسی‌ها
                test_count = min(10, len(proxies))  # حداکثر 10 پروکسی را تست می‌کنیم
                logger.info(f"تست {test_count} پروکسی از {len(proxies)} پروکسی دریافت شده از API خارجی")
                
                # روش امن‌تر: تست ترتیبی با تاخیر
                for i, proxy in enumerate(proxies[:test_count]):
                    logger.info(f"تست پروکسی {i+1}/{test_count}: {proxy.get('host')}:{proxy.get('port')}")
                    try:
                        if test_proxy(proxy, timeout=3):
                            logger.info(f"پروکسی کارآمد از API خارجی پیدا شد: {proxy.get('host')}:{proxy.get('port')}")
                            return proxy
                    except Exception as e:
                        logger.warning(f"خطا در تست پروکسی {i+1}/{test_count}: {e}")
                    
                    # تاخیر کوتاه بین تست‌ها
                    time.sleep(0.2)
                
                # اگر به اینجا رسیدیم، هیچ پروکسی کارآمدی پیدا نشد
                logger.warning(f"هیچ پروکسی کارآمدی از {test_count} پروکسی تست شده پیدا نشد")
                time.sleep(1)  # تاخیر قبل از تلاش مجدد
                
            except requests.exceptions.Timeout:
                logger.warning(f"تایم‌اوت در دریافت پروکسی از API (تلاش {attempt+1}/{max_retries})")
                time.sleep(1)  # تاخیر قبل از تلاش مجدد
            except requests.exceptions.ConnectionError:
                logger.warning(f"خطای اتصال در دریافت پروکسی از API (تلاش {attempt+1}/{max_retries})")
                time.sleep(1)  # تاخیر قبل از تلاش مجدد
            except Exception as e:
                logger.warning(f"خطای نامشخص در دریافت پروکسی از API: {e}")
                break  # در صورت خطاهای نامشخص، خروج از حلقه
                
        # اگر به اینجا رسیدیم، تمام تلاش‌ها ناموفق بوده است
        logger.warning(f"تمام تلاش‌ها برای دریافت پروکسی از API ناموفق بود: {api_url}")
        return None
        
    except Exception as e:
        logger.error(f"خطای کلی در دریافت پروکسی از API: {e}")
        return None

def get_proxy(custom_proxy=None, api_url=None):
    """
    دریافت یک پروکسی برای استفاده در برنامه
    
    Args:
        custom_proxy: رشته پروکسی سفارشی (اختیاری)
        api_url: آدرس API برای دریافت پروکسی (اختیاری)
        
    Returns:
        dict: دیکشنری پروکسی یا None اگر پروکسی موجود نباشد
    """
    # ابتدا اگر URL API ارائه شده باشد، از آن استفاده می‌کنیم
    if api_url:
        proxy = get_proxy_from_api_url(api_url)
        if proxy:
            return proxy
        logger.warning(f"استفاده از URL API ناموفق بود: {api_url}")
    
    # سپس اگر پروکسی سفارشی ارائه شده باشد، آن را پردازش می‌کنیم
    if custom_proxy:
        # بررسی اینکه آیا لیستی از پروکسی‌ها است یا یک پروکسی تکی
        if '\n' in custom_proxy:
            # پردازش لیست پروکسی‌ها
            proxy_list = parse_proxy_list(custom_proxy)
            working_proxy = find_working_proxy_from_list(proxy_list)
            if working_proxy:
                return working_proxy
            logger.warning("هیچ پروکسی کارآمدی در لیست سفارشی پیدا نشد")
        # بررسی اینکه آیا URL است
        elif custom_proxy.startswith(('http://', 'https://')):
            # ممکن است URL یک سرویس پروکسی باشد
            proxy = get_proxy_from_api_url(custom_proxy)
            if proxy:
                return proxy
            logger.warning(f"استفاده از URL پروکسی ناموفق بود: {custom_proxy}")
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