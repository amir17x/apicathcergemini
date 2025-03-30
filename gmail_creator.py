import logging
import time
import random
import os
import re
import traceback
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from selenium.webdriver.common.by import By
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.common.keys import Keys
from selenium.common.exceptions import TimeoutException, NoSuchElementException, StaleElementReferenceException
import undetected_chromedriver as uc
from webdriver_manager.chrome import ChromeDriverManager

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def create_gmail_account(first_name, last_name, username, password, birth_day, birth_month, 
                        birth_year, gender, proxy=None):
    """
    Create a Gmail account using Selenium automation.
    
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
    logger.info(f"Starting Gmail account creation for {username}@gmail.com")
    logger.info(f"Name: {first_name} {last_name}, Birthday: {birth_day}/{birth_month}/{birth_year}, Gender: {gender}")
    
    driver = None
    try:
        # Setup Chrome options
        options = uc.ChromeOptions()
        options.add_argument("--no-sandbox")
        options.add_argument("--disable-dev-shm-usage")
        options.add_argument("--disable-gpu")
        options.add_argument("--window-size=1920,1080")
        options.add_argument("--disable-extensions")
        options.add_argument("--disable-popup-blocking")
        options.add_argument("--disable-blink-features=AutomationControlled")
        options.add_argument("--lang=en-US")
        options.add_argument("--headless")  # بسیار مهم برای اجرا در محیط Replit
        options.add_argument("--user-agent=Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36")
        
        # Configure proxy if provided
        if proxy:
            logger.info(f"Using proxy: {proxy}")
            if isinstance(proxy, dict):
                proxy_string = f"{proxy.get('protocol', 'http')}://{proxy.get('host')}:{proxy.get('port')}"
                if proxy.get('username') and proxy.get('password'):
                    auth = f"{proxy['username']}:{proxy['password']}"
                    options.add_argument(f'--proxy-server={proxy_string}')
                    # Add proxy authentication extension
                    # Code for proxy auth extension would go here
                else:
                    options.add_argument(f'--proxy-server={proxy_string}')
            else:
                # Assuming proxy is a string in format protocol://host:port
                options.add_argument(f'--proxy-server={proxy}')
        
        # Initialize the driver with our custom ChromeDriver
        logger.info("Initializing undetected-chromedriver with custom ChromeDriver...")
        # Set ChromeDriver path from ~/bin if it exists
        chromedriver_path = os.path.expanduser("~/bin/chromedriver")
        if os.path.exists(chromedriver_path):
            logger.info(f"Using custom ChromeDriver from {chromedriver_path}")
            driver = uc.Chrome(driver_executable_path=chromedriver_path, options=options)
        else:
            # Fallback to default method
            logger.info("Custom ChromeDriver not found, using default method")
            driver = uc.Chrome(options=options)
        
        # Set default wait time
        wait = WebDriverWait(driver, 15)
        
        # Navigate to Gmail signup page
        logger.info("Navigating to Gmail signup page...")
        driver.get("https://accounts.google.com/signup")
        time.sleep(2)  # Wait for page to load
        
        # Start filling out the form
        logger.info("Starting form fill process...")
        
        # Fill first name
        logger.info("Filling first name...")
        first_name_field = wait.until(EC.presence_of_element_located((By.NAME, "firstName")))
        first_name_field.clear()
        first_name_field.send_keys(first_name)
        time.sleep(1)
        
        # Fill last name
        logger.info("Filling last name...")
        last_name_field = wait.until(EC.presence_of_element_located((By.NAME, "lastName")))
        last_name_field.clear()
        last_name_field.send_keys(last_name)
        time.sleep(1)
        
        # Click next
        logger.info("Clicking next button...")
        next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']/parent::button")))
        next_button.click()
        time.sleep(3)
        
        # Enter birthday information
        logger.info("Entering birthday information...")
        try:
            # Month select
            month_dropdown = wait.until(EC.presence_of_element_located((By.ID, "month")))
            month_dropdown.click()
            time.sleep(1)
            # Select the month based on the index (value is usually 1-12)
            month_option = wait.until(EC.presence_of_element_located((By.XPATH, f"//select[@id='month']/option[@value='{int(birth_month)}']")))
            month_option.click()
            time.sleep(1)
            
            # Day input
            day_input = wait.until(EC.presence_of_element_located((By.ID, "day")))
            day_input.clear()
            day_input.send_keys(birth_day)
            time.sleep(1)
            
            # Year input
            year_input = wait.until(EC.presence_of_element_located((By.ID, "year")))
            year_input.clear()
            year_input.send_keys(birth_year)
            time.sleep(1)
            
            # Gender select
            gender_dropdown = wait.until(EC.presence_of_element_located((By.ID, "gender")))
            gender_dropdown.click()
            time.sleep(1)
            
            # Maps 'male' or 'female' to the actual value in the dropdown
            gender_map = {
                'male': '1',   # Assuming 1 is the value for Male
                'female': '2'  # Assuming 2 is the value for Female
            }
            gender_value = gender_map.get(gender.lower(), '3')  # Default to 'Rather not say' (3)
            
            gender_option = wait.until(EC.presence_of_element_located((By.XPATH, f"//select[@id='gender']/option[@value='{gender_value}']")))
            gender_option.click()
            time.sleep(1)
            
            # Click next again
            next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']/parent::button")))
            next_button.click()
            time.sleep(3)
        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"Error filling birthday information: {e}")
            return {
                'success': False,
                'error': 'Failed to fill birthday information. Google may have changed their page layout.'
            }
        
        # Choose "Create a new Gmail address" option if presented with an option
        try:
            create_gmail_option = WebDriverWait(driver, 5).until(
                EC.presence_of_element_located((By.XPATH, "//span[contains(text(), 'Create a new Gmail address')]/parent::div")))
            create_gmail_option.click()
            time.sleep(2)
        except (TimeoutException, NoSuchElementException):
            logger.info("Directly on username selection page, no need to select 'Create Gmail' option")
        
        # Enter desired Gmail username
        try:
            logger.info(f"Entering username: {username}")
            username_field = wait.until(EC.presence_of_element_located((By.NAME, "Username")))
            username_field.clear()
            username_field.send_keys(username)
            time.sleep(1)
            
            # Click next
            next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']/parent::button")))
            next_button.click()
            time.sleep(3)
            
            # Check for username availability error
            try:
                error_message = WebDriverWait(driver, 5).until(
                    EC.presence_of_element_located((By.XPATH, "//div[contains(@class, 'o6cuMc')]")))
                error_text = error_message.text
                logger.warning(f"Username error: {error_text}")
                
                if "That username is taken" in error_text:
                    # Try suggested usernames
                    suggested_usernames = driver.find_elements(By.XPATH, "//div[contains(@class, 'aCjZkd')]/span")
                    if suggested_usernames:
                        # Click the first suggested username
                        suggested_usernames[0].click()
                        new_username = wait.until(EC.presence_of_element_located((By.NAME, "Username"))).get_attribute("value")
                        logger.info(f"Selected suggested username: {new_username}")
                        username = new_username  # Update the username variable
                        
                        # Click next again
                        next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']/parent::button")))
                        next_button.click()
                        time.sleep(3)
                    else:
                        return {
                            'success': False,
                            'error': 'Username is taken and no suggestions were provided.'
                        }
                else:
                    return {
                        'success': False,
                        'error': f'Username error: {error_text}'
                    }
            except TimeoutException:
                # No error found, proceed
                logger.info("Username accepted")
        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"Error setting username: {e}")
            return {
                'success': False,
                'error': 'Failed to set username. Google may have changed their page layout.'
            }
        
        # Enter password and confirm
        try:
            logger.info("Entering password")
            
            password_field = wait.until(EC.presence_of_element_located((By.NAME, "Passwd")))
            password_field.clear()
            password_field.send_keys(password)
            time.sleep(1)
            
            confirm_field = wait.until(EC.presence_of_element_located((By.NAME, "PasswdAgain")))
            confirm_field.clear()
            confirm_field.send_keys(password)
            time.sleep(1)
            
            # Click next
            next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[text()='Next']/parent::button")))
            next_button.click()
            time.sleep(3)
        except (TimeoutException, NoSuchElementException) as e:
            logger.error(f"Error setting password: {e}")
            return {
                'success': False,
                'error': 'Failed to set password. Google may have changed their page layout.'
            }
        
        # Check for verification requirement (phone/recovery email)
        if "Verify it's you" in driver.page_source or "verification" in driver.page_source.lower() or "phone" in driver.page_source.lower():
            logger.warning("Phone verification required")
            # Take screenshot for debugging
            screenshot_path = f"/tmp/verification_required_{username}.png"
            driver.save_screenshot(screenshot_path)
            logger.info(f"Screenshot saved to {screenshot_path}")
            
            return {
                'success': False,
                'error': 'Phone verification required. Manual intervention needed.'
            }
        
        # Check for terms of service page
        if "Terms of Service" in driver.page_source or "Privacy and Terms" in driver.page_source:
            logger.info("Accepting terms of service")
            try:
                # Scroll to bottom of terms
                driver.execute_script("window.scrollTo(0, document.body.scrollHeight);")
                time.sleep(1)
                
                # Click accept/next
                next_button = wait.until(EC.element_to_be_clickable((By.XPATH, "//span[contains(text(), 'I agree') or contains(text(), 'Accept')]/parent::button")))
                next_button.click()
                time.sleep(5)
            except (TimeoutException, NoSuchElementException) as e:
                logger.error(f"Error accepting terms of service: {e}")
                return {
                    'success': False,
                    'error': 'Failed to accept terms of service. Manual intervention needed.'
                }
        
        # Check if account was created successfully
        if "Welcome to Google" in driver.page_source or "Your new account" in driver.page_source:
            logger.info(f"Account successfully created: {username}@gmail.com")
            return {
                'success': True,
                'gmail': f"{username}@gmail.com",
                'password': password
            }
        
        # If we reach here, something unexpected happened
        logger.warning("Unexpected page encountered after account creation flow")
        screenshot_path = f"/tmp/unexpected_page_{username}.png"
        driver.save_screenshot(screenshot_path)
        logger.info(f"Screenshot saved to {screenshot_path}")
        
        # Check current URL to determine status
        current_url = driver.current_url
        if "myaccount.google.com" in current_url or "mail.google.com" in current_url:
            logger.info("Detected Google account page, assuming success")
            return {
                'success': True,
                'gmail': f"{username}@gmail.com",
                'password': password
            }
        
        return {
            'success': False,
            'error': 'Failed to create account. Encountered unexpected page in the process.'
        }
        
    except Exception as e:
        logger.error(f"Exception during account creation: {e}")
        logger.error(traceback.format_exc())
        
        # Try to capture screenshot if possible
        if driver:
            try:
                screenshot_path = f"/tmp/error_{username}.png"
                driver.save_screenshot(screenshot_path)
                logger.info(f"Error screenshot saved to {screenshot_path}")
            except:
                pass
        
        return {
            'success': False,
            'error': f'Error creating account: {str(e)}'
        }
    finally:
        # Close the browser
        if driver:
            logger.info("Closing browser")
            try:
                driver.quit()
            except:
                pass
