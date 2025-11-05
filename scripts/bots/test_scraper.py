#!/usr/bin/env python3
import requests
import time
import random
import threading
from concurrent.futures import ThreadPoolExecutor
import json
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class NginxTestBot:
    def __init__(self, base_url="http://localhost:8080"):
        self.base_url = base_url
        self.session = requests.Session()
        
        # Different user agents to simulate various clients
        self.user_agents = [
            "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
            "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
            "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
            "curl/7.68.0",
            "Python-requests/2.25.1"
        ]
        
        # Common paths to test
        self.test_paths = [
            "/",
            "/index.html",
            "/about",
            "/contact",
            "/api/users",
            "/api/data",
            "/images/logo.png",
            "/css/style.css",
            "/js/app.js",
            "/admin",
            "/login",
            "/dashboard"
        ]
        
        # Malicious patterns for testing IDS
        self.malicious_patterns = [
            "/admin/../../../etc/passwd",
            "/index.php?id=1' OR '1'='1",
            "/<script>alert('xss')</script>",
            "/wp-admin/admin-ajax.php",
            "/.env",
            "/config.php",
            "/phpmyadmin/",
            "/sql/",
            "/backup.sql"
        ]

    def make_request(self, path, method="GET", headers=None, params=None, data=None):
        """Make HTTP request and return response details"""
        try:
            url = f"{self.base_url}{path}"
            
            if headers is None:
                headers = {
                    'User-Agent': random.choice(self.user_agents)
                }
            
            response = self.session.request(
                method=method,
                url=url,
                headers=headers,
                params=params,
                data=data,
                timeout=5
            )
            
            return {
                'url': url,
                'method': method,
                'status_code': response.status_code,
                'response_time': response.elapsed.total_seconds(),
                'content_length': len(response.content)
            }
            
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed for {path}: {e}")
            return None

    def normal_traffic(self, duration=60):
        """Generate normal web traffic"""
        logger.info(f"Starting normal traffic generation for {duration} seconds")
        end_time = time.time() + duration
        
        while time.time() < end_time:
            path = random.choice(self.test_paths)
            result = self.make_request(path)
            
            if result:
                logger.info(f"Normal: {result['method']} {result['url']} -> {result['status_code']}")
            
            # Random delay between requests
            time.sleep(random.uniform(0.5, 3.0))

    def suspicious_traffic(self, duration=30):
        """Generate suspicious/malicious traffic"""
        logger.info(f"Starting suspicious traffic generation for {duration} seconds")
        end_time = time.time() + duration
        
        while time.time() < end_time:
            path = random.choice(self.malicious_patterns)
            result = self.make_request(path)
            
            if result:
                logger.warning(f"Suspicious: {result['method']} {result['url']} -> {result['status_code']}")
            
            time.sleep(random.uniform(1.0, 2.0))

    def high_frequency_traffic(self, duration=20, requests_per_second=10):
        """Generate high frequency traffic to test rate limiting"""
        logger.info(f"Starting high frequency traffic: {requests_per_second} req/sec for {duration} seconds")
        
        def make_rapid_requests():
            path = random.choice(self.test_paths[:5])  # Use common paths
            result = self.make_request(path)
            if result:
                logger.info(f"Rapid: {result['status_code']} - {result['response_time']:.3f}s")
        
        with ThreadPoolExecutor(max_workers=requests_per_second) as executor:
            end_time = time.time() + duration
            while time.time() < end_time:
                for _ in range(requests_per_second):
                    executor.submit(make_rapid_requests)
                time.sleep(1)

    def run_comprehensive_test(self):
        """Run a comprehensive test of the pipeline"""
        logger.info("Starting comprehensive pipeline test")
        
        # Test 1: Normal traffic
        normal_thread = threading.Thread(target=self.normal_traffic, args=(120,))
        
        # Test 2: Suspicious traffic
        suspicious_thread = threading.Thread(target=self.suspicious_traffic, args=(60,))
        
        # Start threads
        normal_thread.start()
        time.sleep(10)  # Start suspicious traffic after 10 seconds
        suspicious_thread.start()
        
        # Test 3: High frequency after 30 seconds
        time.sleep(30)
        high_freq_thread = threading.Thread(target=self.high_frequency_traffic, args=(30, 5))
        high_freq_thread.start()
        
        # Wait for all tests to complete
        normal_thread.join()
        suspicious_thread.join()
        high_freq_thread.join()
        
        logger.info("Comprehensive test completed")

if __name__ == "__main__":
    bot = NginxTestBot()
    
    # Run the comprehensive test
    bot.run_comprehensive_test()
    
    logger.info("Test scraper finished. Check nginx logs and pipeline output.")