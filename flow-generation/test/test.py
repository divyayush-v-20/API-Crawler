import os
import json
import time
import requests
from datetime import datetime, timedelta
import re
from urllib.parse import urlparse, parse_qs

class YLEAreenaCrawler:
    def __init__(self):
        # API credentials
        self.app_id = "areena-web-items"
        self.app_key = "wlTs5D9OjIdeS9krPzRQR4I1PYVzoazN"
        self.analytics_app_id = "analytics-sdk"
        self.analytics_app_key = "RVaxtSmiGRRUDos7uAmOCh6fReH9SEyg"
        
        # Common parameters
        self.common_params = {
            "language": "fi",
            "v": "10",
            "client": "yle-areena-web",
            "app_id": self.app_id,
            "app_key": self.app_key
        }
        
        # Headers
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Referer": "https://areena.yle.fi/",
            "sec-ch-ua": "\"Not.A/Brand\";v=\"99\", \"Chromium\";v=\"136\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Linux\""
        }
        
        # Cookies
        self.cookies = {
            "yle_selva": "1749181611342597482"
        }
        
        # Available channels
        self.channels = ["yle-tv1", "yle-tv2", "yle-teema-fem", "tv-finland", "yle-areena"]
        
        # Build ID (will be fetched dynamically)
        self.build_id = None
        
        # User location
        self.location = None
        
        # Output directory
        self.output_dir = "yle_areena_data"
        
    def get_build_id(self):
        """Extract the build ID from the main page"""
        try:
            response = requests.get("https://areena.yle.fi/tv/opas", headers=self.headers, cookies=self.cookies)
            response.raise_for_status()
            
            # Extract build ID using regex
            build_id_match = re.search(r'/_next/static/([^/]+)/_buildManifest\.js', response.text)
            if build_id_match:
                self.build_id = build_id_match.group(1)
                print(f"Found build ID: {self.build_id}")
            else:
                print("Could not find build ID, using fallback method")
                # Try alternative method - extract from any next/data URL
                next_data_match = re.search(r'/_next/data/([^/]+)/', response.text)
                if next_data_match:
                    self.build_id = next_data_match.group(1)
                    print(f"Found build ID (alternative method): {self.build_id}")
                else:
                    raise Exception("Could not extract build ID")
        except Exception as e:
            print(f"Error getting build ID: {e}")
            raise
    
    def get_user_location(self):
        """Get user's geographic location"""
        try:
            params = {
                "app_id": self.analytics_app_id,
                "app_key": self.analytics_app_key
            }
            
            response = requests.get(
                "https://locations.api.yle.fi/v4/address/current",
                params=params,
                headers=self.headers,
                cookies=self.cookies
            )
            response.raise_for_status()
            
            self.location = response.json()
            self.common_params["country"] = self.location.get("country_code", "FI")
            print(f"Location detected: {self.location.get('city', 'Unknown')}, {self.location.get('country_code', 'Unknown')}")
        except Exception as e:
            print(f"Error getting location: {e}")
            print("Using default country code: FI")
            self.common_params["country"] = "FI"
    
    def get_available_dates(self, days=7):
        """Generate a list of dates to crawl (current date + specified number of days)"""
        dates = []
        today = datetime.now()
        
        for i in range(days):
            date = today + timedelta(days=i)
            dates.append(date.strftime("%Y-%m-%d"))
        
        return dates
    
    def get_channel_schedule(self, channel_id, date):
        """Get TV program schedule for a specific channel and date"""
        programs = []
        offset = 0
        limit = 100
        
        while True:
            try:
                params = self.common_params.copy()
                params.update({
                    "yleReferer": f"tv.guide.{date}.tv_opas.{channel_id}.untitled_list",
                    "offset": offset,
                    "limit": limit
                })
                
                url = f"https://areena.api.yle.fi/v1/ui/schedules/{channel_id}/{date}.json"
                
                response = requests.get(
                    url,
                    params=params,
                    headers=self.headers,
                    cookies=self.cookies
                )
                response.raise_for_status()
                
                data = response.json()
                items = data.get("data", [])
                programs.extend(items)
                
                total_count = data.get("meta", {}).get("count", 0)
                
                if offset + limit >= total_count or not items:
                    break
                
                offset += limit
                time.sleep(1)  # Be nice to the server
                
            except Exception as e:
                print(f"Error fetching schedule for {channel_id} on {date}: {e}")
                break
        
        return programs
    
    def extract_program_data(self, program):
        """Extract relevant data from a program object"""
        # Extract program ID from pointer URI
        program_id = None
        if program.get("pointer") and program["pointer"].get("uri"):
            uri_match = re.search(r'yleareena://items/(\S+)', program["pointer"]["uri"])
            if uri_match:
                program_id = uri_match.group(1)
        
        # Extract broadcast times
        start_time = None
        end_time = None
        for label in program.get("labels", []):
            if label.get("type") == "broadcastStartDate" and label.get("raw"):
                start_time = label["raw"]
            elif label.get("type") == "broadcastEndDate" and label.get("raw"):
                end_time = label["raw"]
        
        # Create clean program data
        program_data = {
            "id": program_id,
            "title": program.get("title", "Unknown Title"),
            "description": program.get("description", ""),
            "start_time": start_time,
            "end_time": end_time,
            "uri": program.get("pointer", {}).get("uri", "")
        }
        
        return program_data
    
    def save_program_data(self, channel, date, programs):
        """Save program data to file system"""
        # Create directory structure
        channel_dir = os.path.join(self.output_dir, channel)
        os.makedirs(channel_dir, exist_ok=True)
        
        # Create file for this date
        file_path = os.path.join(channel_dir, f"{date}.json")
        
        # Process all programs
        processed_programs = [self.extract_program_data(program) for program in programs]
        
        # Save to file
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump({
                "channel": channel,
                "date": date,
                "programs": processed_programs
            }, f, ensure_ascii=False, indent=2)
        
        print(f"Saved {len(processed_programs)} programs for {channel} on {date}")
    
    def crawl(self, days=7):
        """Main crawling function"""
        # Create output directory
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Get build ID
        self.get_build_id()
        
        # Get user location
        self.get_user_location()
        
        # Get dates to crawl
        dates = self.get_available_dates(days)
        
        # Crawl each channel for each date
        for channel in self.channels:
            print(f"Crawling channel: {channel}")
            for date in dates:
                print(f"  Date: {date}")
                programs = self.get_channel_schedule(channel, date)
                self.save_program_data(channel, date, programs)
                time.sleep(1)  # Be nice to the server

if __name__ == "__main__":
    # Create and run the crawler
    crawler = YLEAreenaCrawler()
    
    # Crawl data for the next 7 days (modify as needed)
    crawler.crawl(days=7)
    
    print("Crawling completed!")