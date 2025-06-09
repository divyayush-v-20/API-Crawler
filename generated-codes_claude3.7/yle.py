import os
import json
import time
import requests
import datetime
from bs4 import BeautifulSoup
from urllib.parse import urlparse, parse_qs

class YleAreenaCrawler:
    def __init__(self):
        self.base_url = "https://areena.yle.fi"
        self.api_base_url = "https://areena.api.yle.fi"
        self.locations_api_url = "https://locations.api.yle.fi"
        
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
        self.results_dir = "../results_claude3.7/yle"
        
        # Create results directory if it doesn't exist
        os.makedirs(self.results_dir, exist_ok=True)
        
    def get_build_id(self):
        """Extract the build_id from the main page HTML"""
        response = requests.get(f"{self.base_url}/tv/opas", headers=self.headers, cookies=self.cookies)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        # Find script tags with _buildManifest
        scripts = soup.find_all('script')
        for script in scripts:
            if script.get('src') and '_buildManifest' in script.get('src'):
                url_parts = script.get('src').split('/')
                for part in url_parts:
                    if part and part != '_next' and part != 'static':
                        self.build_id = part
                        return self.build_id
        
        # Alternative method: look for next data in the HTML
        for script in soup.find_all('script', id='__NEXT_DATA__'):
            if script and script.string:
                data = json.loads(script.string)
                if 'buildId' in data:
                    self.build_id = data['buildId']
                    return self.build_id
        
        raise Exception("Could not extract build_id from the page")
    
    def get_user_location(self):
        """Get user's geographic location"""
        params = {
            "app_id": "analytics-sdk",
            "app_key": "RVaxtSmiGRRUDos7uAmOCh6fReH9SEyg"
        }
        
        response = requests.get(
            f"{self.locations_api_url}/v4/address/current",
            params=params,
            headers=self.headers,
            cookies=self.cookies
        )
        
        if response.status_code == 200:
            location_data = response.json()
            self.common_params["country"] = location_data.get("country_code", "IN")
            return location_data
        
        return None
    
    def get_available_dates(self, start_date=None):
        """Get available dates for TV guide"""
        if not self.build_id:
            self.get_build_id()
        
        if not start_date:
            start_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        params = {"t": start_date}
        headers = self.headers.copy()
        headers["x-nextjs-data"] = "1"
        
        response = requests.get(
            f"{self.base_url}/_next/data/{self.build_id}/fi/tv/opas.json",
            params=params,
            headers=headers,
            cookies=self.cookies
        )
        
        if response.status_code == 200:
            guide_data = response.json()
            
            # Save the guide data
            with open(f"{self.results_dir}/tv_guide_navigation_{start_date}.json", "w") as f:
                json.dump(guide_data, f, indent=2)
            
            # Extract dates from the navigation
            dates = []
            try:
                page_props = guide_data.get("pageProps", {})
                guide_data = page_props.get("guideData", {})
                date_navigation = guide_data.get("dateNavigation", {})
                
                # Extract dates from the navigation items
                for item in date_navigation.get("items", []):
                    if "date" in item:
                        dates.append(item["date"])
            except Exception as e:
                print(f"Error extracting dates: {e}")
            
            # If no dates found, use a 7-day range from start_date
            if not dates:
                start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
                dates = [(start + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(7)]
            
            return dates
        
        return []
    
    def get_channel_schedule(self, channel_id, date, offset=0, limit=100):
        """Get TV program schedule for a specific channel and date"""
        params = self.common_params.copy()
        params.update({
            "yleReferer": f"tv.guide.{date}.tv_opas.{channel_id}.untitled_list",
            "offset": offset,
            "limit": limit
        })
        
        response = requests.get(
            f"{self.api_base_url}/v1/ui/schedules/{channel_id}/{date}.json",
            params=params,
            headers=self.headers,
            cookies=self.cookies
        )
        
        if response.status_code == 200:
            return response.json()
        
        return None
    
    def get_all_channel_schedules(self, channel_id, date):
        """Get all schedules for a channel on a specific date, handling pagination"""
        all_programs = []
        offset = 0
        limit = 100
        
        while True:
            schedule_data = self.get_channel_schedule(channel_id, date, offset, limit)
            
            if not schedule_data or "data" not in schedule_data:
                break
            
            programs = schedule_data.get("data", [])
            all_programs.extend(programs)
            
            # Check if we need to fetch more
            meta = schedule_data.get("meta", {})
            total_count = meta.get("count", 0)
            
            if offset + limit >= total_count or not programs:
                break
            
            offset += limit
            time.sleep(0.5)  # Add a small delay to avoid rate limiting
        
        return all_programs
    
    def crawl_all_schedules(self, num_days=7):
        """Crawl all channel schedules for a specified number of days"""
        # Get user location first
        location = self.get_user_location()
        
        # Save location data
        with open(f"{self.results_dir}/user_location.json", "w") as f:
            json.dump(location, f, indent=2)
        
        # Get the build ID
        if not self.build_id:
            self.get_build_id()
        
        # Start with today's date
        start_date = datetime.datetime.now().strftime("%Y-%m-%d")
        
        # Get available dates from the guide
        dates = self.get_available_dates(start_date)
        
        # If no dates found or fewer than requested, generate dates
        if len(dates) < num_days:
            start = datetime.datetime.strptime(start_date, "%Y-%m-%d")
            dates = [(start + datetime.timedelta(days=i)).strftime("%Y-%m-%d") for i in range(num_days)]
        
        # Limit to the requested number of days
        dates = dates[:num_days]
        
        all_schedules = {}
        
        # For each date and channel, get the schedule
        for date in dates:
            all_schedules[date] = {}
            
            for channel in self.channels:
                print(f"Crawling schedule for {channel} on {date}")
                
                programs = self.get_all_channel_schedules(channel, date)
                all_schedules[date][channel] = programs
                
                # Save individual channel schedule
                with open(f"{self.results_dir}/{channel}_{date}_schedule.json", "w") as f:
                    json.dump(programs, f, indent=2)
                
                time.sleep(1)  # Add delay between requests
        
        # Save all schedules in a single file
        with open(f"{self.results_dir}/all_schedules.json", "w") as f:
            json.dump(all_schedules, f, indent=2)
        
        return all_schedules

if __name__ == "__main__":
    crawler = YleAreenaCrawler()
    crawler.crawl_all_schedules(num_days=7)
