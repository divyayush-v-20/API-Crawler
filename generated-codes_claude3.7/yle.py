import os
import json
import time
import requests
from datetime import datetime, timedelta
import re
from bs4 import BeautifulSoup

class YleAreenaCrawler:
    def __init__(self):
        self.base_url = "https://areena.yle.fi"
        self.api_base_url = "https://areena.api.yle.fi"
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
            "app_id": "areena-web-items",
            "app_key": "wlTs5D9OjIdeS9krPzRQR4I1PYVzoazN"
        }
        self.channels = ["yle-tv1", "yle-tv2", "yle-teema-fem", "tv-finland", "yle-areena"]
        self.build_id = None
        self.output_dir = "../results_claude3.7/yle"
        os.makedirs(self.output_dir, exist_ok=True)
        
    def get_build_id(self):
        """Extract the build_id from the main page HTML"""
        response = requests.get(self.base_url, headers=self.headers, cookies=self.cookies)
        if response.status_code == 200:
            soup = BeautifulSoup(response.text, 'html.parser')
            # Look for Next.js build ID in script tags
            scripts = soup.find_all('script', {'src': re.compile(r'/_next/static/[^/]+/_buildManifest\.js')})
            if scripts:
                build_id_match = re.search(r'/_next/static/([^/]+)/_buildManifest\.js', scripts[0]['src'])
                if build_id_match:
                    return build_id_match.group(1)
            
            # Alternative method: look for build ID in the HTML
            build_id_match = re.search(r'/_next/data/([^/]+)/fi\.json', response.text)
            if build_id_match:
                return build_id_match.group(1)
        
        raise Exception("Could not extract build_id from the main page")
    
    def get_user_location(self):
        """Get user's geographic location"""
        url = "https://locations.api.yle.fi/v4/address/current"
        params = {
            "app_id": "analytics-sdk",
            "app_key": "RVaxtSmiGRRUDos7uAmOCh6fReH9SEyg"
        }
        response = requests.get(url, params=params, headers=self.headers, cookies=self.cookies)
        if response.status_code == 200:
            return response.json()
        return None
    
    def get_available_dates(self):
        """Get available dates for TV guide"""
        if not self.build_id:
            self.build_id = self.get_build_id()
        
        url = f"{self.base_url}/_next/data/{self.build_id}/fi/tv/opas.json"
        headers = self.headers.copy()
        headers["x-nextjs-data"] = "1"
        
        response = requests.get(url, headers=headers, cookies=self.cookies)
        if response.status_code == 200:
            data = response.json()
            # Extract dates from the navigation elements
            # For simplicity, we'll use the current date and a few days before/after
            today = datetime.now()
            dates = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(-3, 4)]
            return dates
        
        raise Exception(f"Failed to get available dates: {response.status_code}")
    
    def get_channel_schedule(self, channel_id, date):
        """Get TV program schedule for a specific channel on a specific date"""
        url = f"{self.api_base_url}/v1/ui/schedules/{channel_id}/{date}.json"
        params = self.common_params.copy()
        params["yleReferer"] = f"tv.guide.{date}.tv_opas.{channel_id}.untitled_list"
        params["offset"] = 0
        params["limit"] = 100
        
        all_programs = []
        while True:
            response = requests.get(url, params=params, headers=self.headers, cookies=self.cookies)
            if response.status_code == 200:
                data = response.json()
                programs = data.get("data", [])
                all_programs.extend(programs)
                
                # Check if we need to paginate
                meta = data.get("meta", {})
                offset = meta.get("offset", 0)
                limit = meta.get("limit", 100)
                count = meta.get("count", 0)
                
                if offset + limit >= count or not programs:
                    break
                
                # Update offset for next page
                params["offset"] = offset + limit
                time.sleep(0.5)  # Be nice to the server
            else:
                print(f"Failed to get schedule for {channel_id} on {date}: {response.status_code}")
                break
        
        return all_programs
    
    def extract_program_details(self, program):
        """Extract relevant details from a program entry"""
        program_id = None
        if program.get("pointer") and program["pointer"].get("uri"):
            uri = program["pointer"]["uri"]
            program_id = uri.split("/")[-1] if "/" in uri else uri.split(":")[-1]
        
        start_time = None
        end_time = None
        for label in program.get("labels", []):
            if label.get("type") == "broadcastStartDate" and label.get("raw"):
                start_time = label["raw"]
            elif label.get("type") == "broadcastEndDate" and label.get("raw"):
                end_time = label["raw"]
        
        return {
            "id": program_id,
            "title": program.get("title", ""),
            "description": program.get("description", ""),
            "start_time": start_time,
            "end_time": end_time,
            "raw_data": program
        }
    
    def crawl(self):
        """Main crawling function"""
        # Get user location (optional but recommended)
        location = self.get_user_location()
        print(f"User location: {location}")
        
        # Get available dates
        dates = self.get_available_dates()
        print(f"Available dates: {dates}")
        
        # Structure to hold all data
        all_data = {}
        
        # For each date and channel, get the schedule
        for date in dates:
            print(f"Processing date: {date}")
            date_data = {}
            
            for channel in self.channels:
                print(f"  Processing channel: {channel}")
                programs = self.get_channel_schedule(channel, date)
                
                # Process programs
                processed_programs = []
                for program in programs:
                    details = self.extract_program_details(program)
                    processed_programs.append(details)
                
                date_data[channel] = processed_programs
            
            all_data[date] = date_data
            
            # Save data for this date
            with open(os.path.join(self.output_dir, f"yle_schedule_{date}.json"), 'w', encoding='utf-8') as f:
                json.dump(date_data, f, ensure_ascii=False, indent=2)
        
        # Save all data
        with open(os.path.join(self.output_dir, "yle_all_schedules.json"), 'w', encoding='utf-8') as f:
            json.dump(all_data, f, ensure_ascii=False, indent=2)
        
        # Create a hierarchical structure by genre/show/episodes
        self.organize_by_genre()
    
    def organize_by_genre(self):
        """Organize the data by genre/show/episodes"""
        # This is a simplified approach since the API doesn't directly provide genre information
        # We'll use the channel as a top-level category and group by show title
        
        # Load all schedule data
        all_schedules = {}
        for filename in os.listdir(self.output_dir):
            if filename.startswith("yle_schedule_") and filename.endswith(".json"):
                with open(os.path.join(self.output_dir, filename), 'r', encoding='utf-8') as f:
                    date = filename.replace("yle_schedule_", "").replace(".json", "")
                    all_schedules[date] = json.load(f)
        
        # Organize by channel (genre) -> show -> episodes
        hierarchical_data = {}
        
        for date, date_data in all_schedules.items():
            for channel, programs in date_data.items():
                if channel not in hierarchical_data:
                    hierarchical_data[channel] = {}
                
                for program in programs:
                    title = program.get("title", "Unknown")
                    if title not in hierarchical_data[channel]:
                        hierarchical_data[channel][title] = []
                    
                    # Add date information to the episode
                    episode = program.copy()
                    episode["broadcast_date"] = date
                    hierarchical_data[channel][title].append(episode)
        
        # Save hierarchical data
        with open(os.path.join(self.output_dir, "yle_hierarchical.json"), 'w', encoding='utf-8') as f:
            json.dump(hierarchical_data, f, ensure_ascii=False, indent=2)

if __name__ == "__main__":
    crawler = YleAreenaCrawler()
    crawler.crawl()