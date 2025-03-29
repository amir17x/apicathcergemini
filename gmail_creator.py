import logging
import time
import random
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_gmail_account(first_name, last_name, username, password, birth_day, birth_month, 
                        birth_year, gender, proxy=None):
    """
    Create a Gmail account using Selenium.
    
    Args:
        first_name: First name for the account
        last_name: Last name for the account
        username: Desired Gmail username
        password: Password for the account
        birth_day: Day of birth
        birth_month: Month of birth
        birth_year: Year of birth
        gender: Gender selection
        proxy: Optional proxy settings
        
    Returns:
        dict: A dictionary with 'success' status and additional info
    """
    driver = None
    try:
        # Set up Chrome options
        chrome_options = Options()
        chrome_options.add_argument("--headless")  # Run in headless mode
        chrome_options.add_argument("--no-sandbox")
        chrome_options.add_argument("--disable-dev-shm-usage")
        chrome_options.add_argument("--disable-gpu")
        chrome_options.add_argument("--window-size=1920,1080")
        
        # Add user agent to mimic real browser
        chrome_options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                                   "AppleWebKit/537.36 (KHTML, like Gecko) "
                                   "Chrome/92.0.4515.159 Safari/537.36")
        
        # Add proxy if provided
        if proxy and proxy != "default":
            chrome_options.add_argument(f'--proxy-server={proxy}')
        
        # Initialize WebDriver
        driver = webdriver.Chrome(options=chrome_options)
        
        # Set implicit wait
        driver.implicitly_wait(10)
        
        # Open Google account creation page
        logger.info("Opening Google account creation page")
        driver.get("https://accounts.google.com/signup")
        
        # Wait for the form to load
        WebDriverWait(driver, 20).until(
            EC.presence_of_element_located((By.ID, "firstName"))
        )
        
        # Fill in personal information
        logger.info("Filling in personal information")
        driver.find_element(By.ID, "firstName").send_keys(first_name)
        driver.find_element(By.ID, "lastName").send_keys(last_name)
        
        # Click next
        driver.find_element(By.XPATH, "//span[text()='Next']").click()
        
        # Wait for the birthday form
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "day"))
        )
        
        # Fill in birthday
        logger.info("Filling in birthday information")
        driver.find_element(By.ID, "day").send_keys(birth_day)
        
        # Select month
        month_dropdown = driver.find_element(By.ID, "month")
        month_dropdown.click()
        month_option = driver.find_element(By.XPATH, f"//option[contains(text(), '{birth_month}')]")
        month_option.click()
        
        # Fill in year and gender
        driver.find_element(By.ID, "year").send_keys(birth_year)
        
        # Select gender
        gender_dropdown = driver.find_element(By.ID, "gender")
        gender_dropdown.click()
        gender_option = driver.find_element(By.XPATH, f"//option[contains(text(), '{gender}')]")
        gender_option.click()
        
        # Click next
        driver.find_element(By.XPATH, "//span[text()='Next']").click()
        
        # Wait for username form
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "username"))
        )
        
        # Fill in username
        logger.info("Setting up username and password")
        username_field = driver.find_element(By.ID, "username")
        username_field.clear()
        username_field.send_keys(username)
        
        # Fill in password
        driver.find_element(By.NAME, "Passwd").send_keys(password)
        driver.find_element(By.NAME, "PasswdAgain").send_keys(password)
        
        # Click next
        driver.find_element(By.XPATH, "//span[text()='Next']").click()
        
        # Check if phone verification is required
        try:
            phone_verification = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.ID, "phoneNumberId"))
            )
            
            logger.warning("Phone verification required. This automation cannot continue.")
            return {
                'success': False,
                'error': 'Phone verification required. Manual intervention needed.'
            }
        except TimeoutException:
            # No phone verification, continue
            pass
        
        # Accept terms
        try:
            WebDriverWait(driver, 10).until(
                EC.presence_of_element_located((By.XPATH, "//span[text()='I agree']"))
            )
            driver.find_element(By.XPATH, "//span[text()='I agree']").click()
            
            # Wait for account creation to complete
            time.sleep(5)
            
            # Check if we're on the welcome page
            try:
                WebDriverWait(driver, 15).until(
                    EC.presence_of_element_located((By.XPATH, "//h1[contains(text(), 'Welcome')]"))
                )
                logger.info("Gmail account created successfully")
                return {
                    'success': True,
                    'gmail': f"{username}@gmail.com",
                    'password': password
                }
            except TimeoutException:
                # Check for other potential issues
                if "challenge" in driver.current_url:
                    return {
                        'success': False,
                        'error': 'Google challenge detected. Possible bot detection.'
                    }
                else:
                    return {
                        'success': False,
                        'error': 'Failed to verify account creation completion.'
                    }
        except (TimeoutException, NoSuchElementException):
            return {
                'success': False,
                'error': 'Failed to accept terms. Process interrupted.'
            }
        
    except Exception as e:
        logger.error(f"Error creating Gmail account: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        if driver:
            driver.quit()
