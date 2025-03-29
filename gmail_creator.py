import logging
import time
import random
import os
import re

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# For development/testing in Replit environment where Selenium can't run properly
def create_gmail_account(first_name, last_name, username, password, birth_day, birth_month, 
                        birth_year, gender, proxy=None):
    """
    Simulated function for Gmail account creation.
    
    In production, this would use Selenium to automate the creation process.
    For development in Replit, we're using a simulation that returns predefined results.
    
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
    # Log the attempt for debugging
    logger.info(f"Simulating Gmail account creation for {username}@gmail.com")
    logger.info(f"Name: {first_name} {last_name}, Birthday: {birth_day} {birth_month} {birth_year}, Gender: {gender}")
    
    if proxy:
        logger.info(f"Using proxy: {proxy}")
    
    # Simulate potential failure scenarios based on input
    
    # Simulate phone verification requirement (this happens often in real scenarios)
    if random.random() < 0.3:  # 30% chance of phone verification
        logger.warning("Simulated phone verification required")
        return {
            'success': False,
            'error': 'Phone verification required. Manual intervention needed.'
        }
    
    # Simulate detection by Google's bot detection systems
    if random.random() < 0.2:  # 20% chance of being detected as a bot
        logger.warning("Simulated bot detection triggered")
        return {
            'success': False,
            'error': 'Google challenge detected. Possible bot detection.'
        }
    
    # Simulate username already taken
    if username.lower() in ['admin', 'test', 'support', 'john', 'jane']:
        logger.warning(f"Username '{username}' is already taken")
        return {
            'success': False,
            'error': f"The username '{username}' is already taken. Please try another username."
        }
    
    # Simulate proxy failure if using a proxy
    if proxy and random.random() < 0.4:  # 40% chance of proxy failure
        logger.warning("Simulated proxy failure")
        return {
            'success': False,
            'error': 'Connection through proxy failed. Please try a different proxy.'
        }
    
    # If all checks pass, simulate success
    logger.info(f"Simulated successful Gmail account creation: {username}@gmail.com")
    
    return {
        'success': True,
        'gmail': f"{username}@gmail.com",
        'password': password
    }
