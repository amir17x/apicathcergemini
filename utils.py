import random
import string
import logging

# Configure logging
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

# Lists for generating random user information
FIRST_NAMES = ["Alex", "Jordan", "Taylor", "Morgan", "Casey", "Riley", "Jamie", "Avery", 
               "Quinn", "Skyler", "Dakota", "Reese", "Finley", "Rowan", "Parker", "Cameron"]

LAST_NAMES = ["Smith", "Johnson", "Williams", "Brown", "Jones", "Miller", "Davis", 
              "Garcia", "Rodriguez", "Wilson", "Martinez", "Anderson", "Taylor", "Thomas", 
              "Hernandez", "Moore", "Martin", "Jackson", "Thompson", "White"]

GENDERS = ["Male", "Female", "Rather not say"]

MONTHS = ["January", "February", "March", "April", "May", "June", 
          "July", "August", "September", "October", "November", "December"]

def generate_random_username(first_name, last_name):
    """Generate a random username based on first and last name with numbers."""
    first = first_name.lower()
    last = last_name.lower()
    random_digits = ''.join(random.choices(string.digits, k=random.randint(3, 5)))
    
    username_patterns = [
        f"{first}.{last}{random_digits}",
        f"{first}{last}{random_digits}",
        f"{first[0]}{last}{random_digits}",
        f"{first}_{last}{random_digits}",
        f"{first}{random_digits}",
        f"{first}{last[0]}{random_digits}"
    ]
    
    return random.choice(username_patterns)

def generate_random_password():
    """Generate a secure random password."""
    length = random.randint(12, 16)
    lowercase = string.ascii_lowercase
    uppercase = string.ascii_uppercase
    digits = string.digits
    special = "!@#$%^&*-_"
    
    # Ensure at least one of each character type
    password = [
        random.choice(lowercase),
        random.choice(uppercase),
        random.choice(digits),
        random.choice(special)
    ]
    
    # Fill the rest of the password
    remaining_length = length - len(password)
    all_chars = lowercase + uppercase + digits + special
    password.extend(random.choices(all_chars, k=remaining_length))
    
    # Shuffle the password
    random.shuffle(password)
    
    return ''.join(password)

def generate_random_user_info():
    """Generate random user information for account creation."""
    first_name = random.choice(FIRST_NAMES)
    last_name = random.choice(LAST_NAMES)
    username = generate_random_username(first_name, last_name)
    password = generate_random_password()
    birth_day = str(random.randint(1, 28))
    birth_month = random.choice(MONTHS)
    # Generate year between 1985 and 2000
    birth_year = str(random.randint(1985, 2000))
    gender = random.choice(GENDERS)
    
    user_info = {
        'first_name': first_name,
        'last_name': last_name,
        'username': username,
        'password': password,
        'birth_day': birth_day,
        'birth_month': birth_month,
        'birth_year': birth_year,
        'gender': gender
    }
    
    logger.debug(f"Generated random user info: {user_info}")
    return user_info

def setup_proxy(proxy_string):
    """
    Convert proxy string to a format suitable for Selenium.
    
    Args:
        proxy_string: String in format 'protocol://username:password@host:port'
        
    Returns:
        dict: Proxy configuration for Selenium
    """
    if not proxy_string or proxy_string == "default":
        return None
        
    try:
        # Parse the proxy string
        if '@' in proxy_string:
            # Proxy with authentication
            auth_part, address_part = proxy_string.split('@')
            protocol = auth_part.split('://')[0]
            
            if ':' in address_part:
                host, port = address_part.split(':')
                
                return {
                    'proxyType': protocol,
                    'httpProxy': f"{host}:{port}",
                    'sslProxy': f"{host}:{port}",
                    'socksProxy': f"{host}:{port}" if protocol == 'socks5' else None
                }
        else:
            # Proxy without authentication
            if '://' in proxy_string:
                protocol, address = proxy_string.split('://')
                
                if ':' in address:
                    host, port = address.split(':')
                    
                    return {
                        'proxyType': protocol,
                        'httpProxy': f"{host}:{port}",
                        'sslProxy': f"{host}:{port}",
                        'socksProxy': f"{host}:{port}" if protocol == 'socks5' else None
                    }
    
    except Exception as e:
        logger.error(f"Error parsing proxy string: {str(e)}")
        return None
    
    logger.error(f"Invalid proxy format: {proxy_string}")
    return None
