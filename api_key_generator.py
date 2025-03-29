import logging
import time
from selenium import webdriver
from selenium.webdriver.common.by import By
from selenium.webdriver.chrome.options import Options
from selenium.webdriver.support.ui import WebDriverWait
from selenium.webdriver.support import expected_conditions as EC
from selenium.common.exceptions import TimeoutException, NoSuchElementException, WebDriverException

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

def generate_api_key(gmail, password, proxy=None):
    """
    Generate a Google Gemini API key using Selenium.
    
    Args:
        gmail: Gmail address for login
        password: Password for the Gmail account
        proxy: Optional proxy settings
        
    Returns:
        dict: A dictionary with 'success' status and API key or error information
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
        
        # Step 1: Login to Google account
        logger.info(f"Attempting to log in with: {gmail}")
        driver.get("https://accounts.google.com/signin")
        
        # Enter email
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.ID, "identifierId"))
        )
        driver.find_element(By.ID, "identifierId").send_keys(gmail)
        driver.find_element(By.XPATH, "//span[text()='Next']").click()
        
        # Enter password
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.NAME, "Passwd"))
        )
        driver.find_element(By.NAME, "Passwd").send_keys(password)
        driver.find_element(By.XPATH, "//span[text()='Next']").click()
        
        # Wait for login to complete
        time.sleep(5)
        
        # Check if login was successful
        if "myaccount.google.com" not in driver.current_url and "signin/v2/challenge" in driver.current_url:
            logger.error("Login failed: Additional verification required")
            return {
                'success': False,
                'error': 'Login failed: Additional verification required'
            }
        
        # Step 2: Navigate to Google AI Studio and generate API key
        logger.info("Navigating to Google AI Studio")
        driver.get("https://aistudio.google.com/app/apikey")
        
        # Wait for API key page to load
        try:
            WebDriverWait(driver, 15).until(
                EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Create API key')]"))
            )
        except TimeoutException:
            # Check if we're on the right page or if additional steps are needed
            if "consent" in driver.current_url:
                logger.info("Consent page detected. Accepting terms.")
                try:
                    # Try to accept terms if on consent page
                    agree_button = driver.find_element(By.XPATH, "//button[contains(text(), 'I agree')]")
                    agree_button.click()
                    
                    # Wait again for the API key page
                    WebDriverWait(driver, 15).until(
                        EC.presence_of_element_located((By.XPATH, "//button[contains(text(), 'Create API key')]"))
                    )
                except (TimeoutException, NoSuchElementException):
                    logger.error("Failed to navigate to API key page after consent")
                    return {
                        'success': False,
                        'error': 'Failed to navigate to API key page after accepting terms'
                    }
            else:
                logger.error("Failed to navigate to API key page")
                return {
                    'success': False,
                    'error': 'Failed to navigate to API key page'
                }
        
        # Click on Create API key button
        create_button = driver.find_element(By.XPATH, "//button[contains(text(), 'Create API key')]")
        create_button.click()
        
        # Wait for the API key to be generated and displayed
        WebDriverWait(driver, 10).until(
            EC.presence_of_element_located((By.XPATH, "//input[contains(@aria-label, 'API key')]"))
        )
        
        # Get the API key
        api_key_input = driver.find_element(By.XPATH, "//input[contains(@aria-label, 'API key')]")
        api_key = api_key_input.get_attribute("value")
        
        if not api_key:
            # Try to find it in another way if the input field doesn't have the value
            api_key_element = driver.find_element(By.XPATH, "//code")
            api_key = api_key_element.text
        
        if not api_key:
            logger.error("Failed to retrieve API key")
            return {
                'success': False,
                'error': 'API key was generated but could not be retrieved'
            }
        
        logger.info("API key generated successfully")
        return {
            'success': True,
            'api_key': api_key
        }
        
    except Exception as e:
        logger.error(f"Error generating API key: {str(e)}")
        return {
            'success': False,
            'error': str(e)
        }
    finally:
        if driver:
            driver.quit()
