#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
ماژول بررسی اعتبار API Key های Google Gemini.
این ماژول برای تست اعتبار و کارکرد صحیح API Key های دریافتی استفاده می‌شود.
"""

import json
import logging
import requests
import time
from typing import Tuple, Dict, Any, Optional, List, Union

# تنظیم لاگینگ
logging.basicConfig(level=logging.DEBUG, 
                    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class GeminiAPIValidator:
    """کلاس مدیریت اعتبارسنجی API Key های Google Gemini."""
    
    def __init__(self):
        """مقداردهی اولیه کلاس اعتبارسنجی Gemini API."""
        self.api_base_url = "https://generativelanguage.googleapis.com/v1"
        self.models_url = f"{self.api_base_url}/models"
        self.test_prompt = "سلام، حالت چطوره؟"
        logger.info("GeminiAPIValidator initialized")
    
    def validate_api_key(self, api_key: str) -> Tuple[bool, Dict[str, Any]]:
        """
        بررسی اعتبار یک API Key از Google Gemini.
        
        Args:
            api_key: کلید API که می‌خواهیم اعتبار آن را بررسی کنیم
            
        Returns:
            Tuple[bool, Dict[str, Any]]: وضعیت اعتبار و اطلاعات بیشتر
        """
        try:
            # تست دسترسی به API با استفاده از درخواست لیست مدل‌ها
            response = requests.get(
                f"{self.models_url}?key={api_key}",
                timeout=10
            )
            
            # بررسی کد وضعیت پاسخ
            if response.status_code == 200:
                logger.info(f"API key validation successful: {api_key[:5]}...")
                return True, {
                    'is_valid': True,
                    'status_code': response.status_code,
                    'models_available': len(response.json().get('models', [])),
                    'response': response.json()
                }
            else:
                logger.warning(f"API key validation failed with status {response.status_code}: {api_key[:5]}...")
                return False, {
                    'is_valid': False,
                    'status_code': response.status_code,
                    'error': response.text
                }
                
        except Exception as e:
            logger.error(f"Error during API key validation: {e}")
            return False, {
                'is_valid': False,
                'error': str(e)
            }
    
    def test_api_completion(self, api_key: str, prompt: str = "سلام، حالت چطوره؟") -> Tuple[bool, Dict[str, Any]]:
        """
        تست عملکرد واقعی API Key با ارسال یک درخواست تکمیل متن.
        
        Args:
            api_key: کلید API که می‌خواهیم آن را تست کنیم
            prompt: متن ورودی برای درخواست تکمیل (پیش‌فرض: "سلام، حالت چطوره؟")
            
        Returns:
            Tuple[bool, Dict[str, Any]]: وضعیت موفقیت و اطلاعات بیشتر
        """
        try:
            # URL برای درخواست تکمیل
            generate_url = f"{self.api_base_url}/models/gemini-pro:generateContent?key={api_key}"
            
            # ساختار درخواست
            payload = {
                "contents": [
                    {
                        "parts": [
                            {
                                "text": prompt
                            }
                        ]
                    }
                ],
                "generationConfig": {
                    "temperature": 0.9,
                    "topK": 32,
                    "topP": 0.95,
                    "maxOutputTokens": 100,
                }
            }
            
            # ارسال درخواست
            response = requests.post(
                generate_url,
                json=payload,
                timeout=15,
                headers={"Content-Type": "application/json"}
            )
            
            # بررسی پاسخ
            if response.status_code == 200:
                response_data = response.json()
                generated_text = ""
                
                # استخراج متن تولید شده
                try:
                    candidates = response_data.get('candidates', [])
                    if candidates and len(candidates) > 0:
                        parts = candidates[0].get('content', {}).get('parts', [])
                        if parts and len(parts) > 0:
                            generated_text = parts[0].get('text', '')
                except Exception as e:
                    logger.warning(f"Error parsing generation response: {e}")
                
                logger.info(f"API completion test successful. Generated text length: {len(generated_text)} characters")
                return True, {
                    'is_working': True,
                    'status_code': response.status_code,
                    'generated_text': generated_text,
                    'response': response_data
                }
            else:
                logger.warning(f"API completion test failed with status {response.status_code}")
                return False, {
                    'is_working': False,
                    'status_code': response.status_code,
                    'error': response.text
                }
                
        except Exception as e:
            logger.error(f"Error during API completion test: {e}")
            return False, {
                'is_working': False,
                'error': str(e)
            }
    
    def get_api_key_details(self, api_key: str) -> Dict[str, Any]:
        """
        دریافت اطلاعات کامل در مورد یک API Key شامل اعتبار و قابلیت‌ها.
        
        Args:
            api_key: کلید API که می‌خواهیم اطلاعات آن را دریافت کنیم
            
        Returns:
            Dict[str, Any]: اطلاعات کامل API Key
        """
        # نتایج اولیه
        results = {
            'api_key_prefix': api_key[:5] + '...' if api_key else None,
            'timestamp': time.time()
        }
        
        # بررسی اعتبار API Key
        is_valid, validation_details = self.validate_api_key(api_key)
        results.update({
            'is_valid': is_valid,
            'validation_details': validation_details
        })
        
        # اگر API Key معتبر است، تست عملکرد واقعی را انجام می‌دهیم
        if is_valid:
            is_working, completion_details = self.test_api_completion(api_key)
            results.update({
                'is_working': is_working,
                'completion_details': completion_details
            })
        else:
            results.update({
                'is_working': False,
                'completion_details': {
                    'error': 'API key is not valid, skipping completion test'
                }
            })
        
        return results


# برای تست مستقیم
if __name__ == "__main__":
    api_key = input("Enter the API key to validate: ")
    validator = GeminiAPIValidator()
    result = validator.get_api_key_details(api_key)
    print(json.dumps(result, indent=2, ensure_ascii=False))