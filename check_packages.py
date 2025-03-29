import sys
import importlib.util

def check_package(package_name):
    try:
        spec = importlib.util.find_spec(package_name)
        if spec is not None:
            print(f"✅ Package '{package_name}' is installed.")
            return True
        else:
            print(f"❌ Package '{package_name}' is not installed.")
            return False
    except ImportError:
        print(f"❌ Error checking package '{package_name}'.")
        return False

# List all packages to check
packages = [
    "telegram", 
    "python_telegram_bot",
    "telegram.ext", 
    "python_telegram_bot.ext"
]

print("Checking installed packages:")
for package in packages:
    check_package(package)

print("\nInstalled packages in sys.modules:")
telegram_modules = [m for m in sys.modules.keys() if 'telegram' in m]
for module in telegram_modules:
    print(f"- {module}")