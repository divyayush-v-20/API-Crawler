import os
import json
import time
import requests
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup

class YleAreenaCrawler:
    def __init__(self):
        # API credentials
        self.app_id = "areena-web-items"
        self.app_key = "wlTs5D9OjIdeS9krPzRQR4I1PYVzoazN"
        
        # Common headers and parameters
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Referer": "https://areena.yle.fi/",
            "sec-ch-ua": "\"Not.A/Brand\";v=\"99\", \"Chromium\";v=\"136\"",
            "sec-ch-ua-mobile": "?0",
            "sec-ch-ua-platform": "\"Linux\""
        }
        
        self.cookies = {
            "yle_selva": "1749181611342597482"
        }
        
        self.common_params = {
            "language": "fi",
            "v": "10",
            "client": "yle-areena-web",
            "country": "IN",
            "app_id": self.app_id,
            "app_key": self.app_key
        }
        
        # Available channels
        self.channels = [
            "yle-tv1",
            "yle-tv2",
            "yle-teema-fem",
            "tv-finland",
            "yle-areena"
        ]
        
        # Output directory
        self.output_dir = "yle_areena_data"
        
        # Get build ID for Next.js API calls
        self.build_id = self._get_build_id()
        
        # Get user location
        self.location = self._get_user_location()
        
    def _get_build_id(self):
        """Extract the build ID from the main page HTML"""
        try:
            response = requests.get("https://areena.yle.fi/tv/opas", headers=self.headers, cookies=self.cookies)
            response.raise_for_status()
            
            # Extract build ID using regex
            build_id_match = re.search(r'"buildId":"([^"]+)"', response.text)
            if build_id_match:
                return build_id_match.group(1)
            
            # Alternative method using BeautifulSoup
            soup = BeautifulSoup(response.text, 'html.parser')
            scripts = soup.find_all('script', {'id': '__NEXT_DATA__'})
            if scripts:
                data = json.loads(scripts[0].string)
                return data.get('buildId')
                
            print("Warning: Could not extract build ID, using fallback")
            return "Q_35nL8jUwGOhxPC9wVX5"  # Fallback build ID
        except Exception as e:
            print(f"Error getting build ID: {e}")
            return "Q_35nL8jUwGOhxPC9wVX5"  # Fallback build ID
    
    def _get_user_location(self):
        """Get user location information"""
        try:
            location_params = {
                "app_id": "analytics-sdk",
                "app_key": "RVaxtSmiGRRUDos7uAmOCh6fReH9SEyg"
            }
            
            response = requests.get(
                "https://locations.api.yle.fi/v4/address/current",
                params=location_params,
                headers=self.headers,
                cookies=self.cookies
            )
            
            if response.status_code == 200:
                return response.json()
            return {"country_code": "IN"}  # Default fallback
        except Exception as e:
            print(f"Error getting location: {e}")
            return {"country_code": "IN"}  # Default fallback
    
    def _get_available_dates(self, days=7):
        """Get a list of available dates for TV schedules"""
        today = datetime.now()
        dates = []
        
        # Get dates for the past 3 days and next 3 days
        for i in range(-3, days-3):
            date = today + timedelta(days=i)
            dates.append(date.strftime("%Y-%m-%d"))
        
        return dates
    
    def _get_channel_schedule(self, channel_id, date):
        """Get the TV schedule for a specific channel and date"""
        all_programs = []
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
                
                if response.status_code != 200:
                    print(f"Error fetching schedule for {channel_id} on {date}: {response.status_code}")
                    break
                
                data = response.json()
                programs = data.get("data", [])
                all_programs.extend(programs)
                
                # Check if we need to fetch more pages
                meta = data.get("meta", {})
                count = meta.get("count", 0)
                
                if offset + limit >= count or not programs:
                    break
                
                offset += limit
                time.sleep(0.5)  # Be nice to the API
                
            except Exception as e:
                print(f"Error fetching schedule for {channel_id} on {date}: {e}")
                break
        
        return all_programs
    
    def _process_program(self, program):
        """Process a program entry and extract relevant information"""
        title = program.get("title", "Unknown Title")
        description = program.get("description", "")
        
        # Extract program ID from pointer URI
        pointer = program.get("pointer", {})
        uri = pointer.get("uri", "")
        program_id = uri.split("/")[-1] if uri else ""
        
        # Extract broadcast times
        start_time = None
        end_time = None
        
        for label in program.get("labels", []):
            if label.get("type") == "broadcastStartDate" and "raw" in label:
                start_time = label["raw"]
            elif label.get("type") == "broadcastEndDate" and "raw" in label:
                end_time = label["raw"]
        
        return {
            "title": title,
            "description": description,
            "id": program_id,
            "start_time": start_time,
            "end_time": end_time,
            "uri": uri
        }
    
    def _create_directory(self, path):
        """Create directory if it doesn't exist"""
        if not os.path.exists(path):
            os.makedirs(path)
    
    def _save_program_data(self, program_data, channel, date):
        """Save program data to file"""
        channel_dir = os.path.join(self.output_dir, channel)
        self._create_directory(channel_dir)
        
        date_dir = os.path.join(channel_dir, date)
        self._create_directory(date_dir)
        
        # Create a safe filename from the title
        title = program_data["title"]
        safe_title = re.sub(r'[^\w\s-]', '', title).strip().replace(' ', '_')
        
        # Add start time to filename to ensure uniqueness and chronological order
        if program_data["start_time"]:
            start_time = datetime.fromisoformat(program_data["start_time"].replace('Z', '+00:00'))
            time_str = start_time.strftime("%H%M")
            filename = f"{time_str}_{safe_title}.json"
        else:
            filename = f"{safe_title}.json"
        
        file_path = os.path.join(date_dir, filename)
        
        with open(file_path, 'w', encoding='utf-8') as f:
            json.dump(program_data, f, ensure_ascii=False, indent=2)
    
    def crawl(self):
        """Main crawling function"""
        print("Starting YLE Areena TV Schedule Crawler")
        print(f"Build ID: {self.build_id}")
        print(f"Location: {self.location.get('country_code', 'Unknown')}")
        
        # Create output directory
        self._create_directory(self.output_dir)
        
        # Get available dates
        dates = self._get_available_dates()
        print(f"Crawling schedules for dates: {', '.join(dates)}")
        
        # Crawl each channel for each date
        for channel in self.channels:
            print(f"\nProcessing channel: {channel}")
            
            for date in dates:
                print(f"  Date: {date}")
                programs = self._get_channel_schedule(channel, date)
                print(f"  Found {len(programs)} programs")
                
                for program in programs:
                    processed_program = self._process_program(program)
                    self._save_program_data(processed_program, channel, date)
                
                time.sleep(1)  # Be nice to the API
        
        print("\nCrawling completed successfully!")

if __name__ == "__main__":
    crawler = YleAreenaCrawler()
    crawler.crawl()