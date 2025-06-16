import requests
import json
import os
import re
from datetime import datetime, timedelta
import time
from urllib.parse import quote

class CTVCrawler:
    def __init__(self):
        self.base_url = "https://www.ctv.ca"
        self.capi_base_url = "https://capi.9c9media.com"
        self.graphql_url = f"{self.base_url}/space-graphql/apq/graphql"
        self.results_dir = "ctv_results"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "sec-ch-ua-platform": "Linux",
            "sec-ch-ua": "\"Not.A/Brand\";v=\"99\", \"Chromium\";v=\"136\"",
            "sec-ch-ua-mobile": "?0",
            "referer": f"{self.base_url}/on-air?tab=schedule"
        }
        self.smart_id = None
        self.channel_mapping = self._get_channel_mapping()
        
        # Create results directory if it doesn't exist
        if not os.path.exists(self.results_dir):
            os.makedirs(self.results_dir)

    def _get_channel_mapping(self):
        """Return mapping of channel names to their hub and code"""
        return {
            "CTV Wild": {"hub": "ctvwild_hub", "code": "WILD-G"},
            "CTV Nature": {"hub": "ctvnature_hub", "code": "NATURE-G"},
            "CTV Speed": {"hub": "ctvspeed_hub", "code": "SPEED-G"},
            "CTV Much": {"hub": "ctvmuch_hub", "code": "MUCHHD-G"},
            "E!": {"hub": "e_hub", "code": "ECANHD-G"},
            "CTV Drama": {"hub": "ctvdrama_hub", "code": "BRAVOC-G"},
            "CTV Windsor": {"hub": "ctv_hub", "code": "CHWI-G"},
            "CTV Regina": {"hub": "ctv_hub", "code": "CICC-G"},
            "CTV Sci-Fi": {"hub": "ctvscifi_hub", "code": "SPCECHD-G"},
            "CTV Comedy": {"hub": "ctvcomedy_hub", "code": "CMDY-G"},
            "Oxygen": {"hub": "oxygen_hub", "code": "OXYG-G"},
            "USA Network": {"hub": "usa_hub", "code": "USA-G"},
            "CTV Life": {"hub": "ctvlife_hub", "code": "LIFEH-G"},
            "CTV British Columbia (interior)": {"hub": "ctv_hub", "code": "CIVTI-G"},
            "CTV Calgary": {"hub": "ctv_hub", "code": "CFCN-G"},
            "CTV Edmonton": {"hub": "ctv_hub", "code": "CFRN-G"},
            "CTV Kitchener": {"hub": "ctv_hub", "code": "CKCO-G"},
            "CTV Lethbridge": {"hub": "ctv_hub", "code": "CFCN-L-G"},
            "CTV Montreal": {"hub": "ctv_hub", "code": "CFCF-G"},
            "CTV Northern Ontario": {"hub": "ctv_hub", "code": "CICI-G"},
            "CTV Ottawa": {"hub": "ctv_hub", "code": "CJOH-G"},
            "CTV Prince Albert": {"hub": "ctv_hub", "code": "CIPA-G"},
            "CTV Saskatoon": {"hub": "ctv_hub", "code": "CFQC-G"},
            "CTV Toronto": {"hub": "ctv_hub", "code": "CFTO-G"},
            "CTV Vancouver": {"hub": "ctv_hub", "code": "CIVT-G"},
            "CTV Vancouver Island": {"hub": "ctv_hub", "code": "CIVI-G"},
            "CTV Winnipeg": {"hub": "ctv_hub", "code": "CKY-G"},
            "CTV Yorkton": {"hub": "ctv_hub", "code": "CICC-G"}
        }

    def sanitize_filename(self, filename):
        """Sanitize filename by replacing spaces with underscores and removing special characters"""
        # Replace spaces with underscores
        filename = filename.replace(' ', '_')
        # Remove special characters
        filename = re.sub(r'[^\w\-.]', '', filename)
        return filename

    def get_smart_id(self):
        """Get API keys needed for subsequent API calls"""
        url = f"{self.base_url}/api/smart-id"
        response = requests.get(url, headers=self.headers)
        
        if response.status_code == 200:
            self.smart_id = response.json()
            return self.smart_id
        else:
            print(f"Failed to get smart ID. Status code: {response.status_code}")
            return None

    def get_channel_collections(self):
        """Get list of available channels and their identifiers"""
        url = f"{self.capi_base_url}/destinations/ctv_hub/platforms/atexace/collections/4126/contents"
        params = {
            "$include": "[Id,Tags,Media.Id]",
            "ContentPackages.Constraints.Geo.PostalCode": "M5V"
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to get channel collections. Status code: {response.status_code}")
            return None

    def get_channel_schedule(self, channel_name, start_date, end_date):
        """Get TV listings for a specific channel for a given date range"""
        if channel_name not in self.channel_mapping:
            print(f"Channel {channel_name} not found in mapping")
            return None
            
        channel_info = self.channel_mapping[channel_name]
        hub = channel_info["hub"]
        code = channel_info["code"]
        
        # Format dates for API
        start_time = f"{start_date}T00:00:00-04:00"
        end_time = f"{end_date}T23:59:59-04:00"
        
        url = f"{self.capi_base_url}/destinations/{hub}/platforms/atexace/channelaffiliates/{code}/schedules"
        params = {
            "StartTime": start_time,
            "EndTime": end_time,
            "$include": "[details]"
        }
        
        response = requests.get(url, headers=self.headers, params=params)
        
        if response.status_code == 200:
            return response.json()
        else:
            print(f"Failed to get schedule for {channel_name}. Status code: {response.status_code}")
            return None

    def save_schedule_data(self, channel_name, data):
        """Save schedule data to appropriate files"""
        if not data or "Items" not in data:
            print(f"No items found in data for {channel_name}")
            return
            
        # Create channel directory
        channel_dir = os.path.join(self.results_dir, self.sanitize_filename(channel_name))
        if not os.path.exists(channel_dir):
            os.makedirs(channel_dir)
            
        # Process each item in the schedule
        for item in data["Items"]:
            entity_type = item.get("EntityType", "Unknown")
            sub_type = item.get("SubType", "Unknown")
            
            if entity_type == "Episode" and sub_type == "Series":
                # TV Series - organize by show name
                show_name = item.get("Name", "Unknown_Show")
                episode_title = item.get("Title", f"Episode_{item.get('EpisodeNumber', 'Unknown')}")
                
                show_dir = os.path.join(channel_dir, self.sanitize_filename(show_name))
                if not os.path.exists(show_dir):
                    os.makedirs(show_dir)
                
                # Add timestamp to ensure uniqueness for episodes with same title
                timestamp = item.get("StartTime", "").replace(":", "-").replace("+", "_plus_")
                filename = f"{self.sanitize_filename(episode_title)}_{timestamp}.json"
                filepath = os.path.join(show_dir, filename)
                
            elif entity_type == "Movie":
                # Movies - save directly in movies folder
                movie_dir = os.path.join(channel_dir, "movies")
                if not os.path.exists(movie_dir):
                    os.makedirs(movie_dir)
                
                movie_title = item.get("Name", "Unknown_Movie")
                # Add timestamp to ensure uniqueness
                timestamp = item.get("StartTime", "").replace(":", "-").replace("+", "_plus_")
                filename = f"{self.sanitize_filename(movie_title)}_{timestamp}.json"
                filepath = os.path.join(movie_dir, filename)
                
            else:
                # Other content types
                content_dir = os.path.join(channel_dir, self.sanitize_filename(sub_type))
                if not os.path.exists(content_dir):
                    os.makedirs(content_dir)
                
                content_title = item.get("Name", "Unknown_Content")
                # Add timestamp to ensure uniqueness
                timestamp = item.get("StartTime", "").replace(":", "-").replace("+", "_plus_")
                filename = f"{self.sanitize_filename(content_title)}_{timestamp}.json"
                filepath = os.path.join(content_dir, filename)
            
            # Save the item data to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(item, f, indent=2)
                
            print(f"Saved: {filepath}")

    def crawl_schedules(self, days_back=7):
        """Crawl TV schedules for the specified number of days back"""
        # Get API keys
        self.get_smart_id()
        
        # Get today's date
        today = datetime.now()
        
        # For each channel in our mapping
        for channel_name in self.channel_mapping:
            print(f"\nCrawling data for channel: {channel_name}")
            
            # For each day in the range
            for day_offset in range(days_back, -1, -1):
                target_date = today - timedelta(days=day_offset)
                date_str = target_date.strftime("%Y-%m-%d")
                
                print(f"  Getting schedule for {date_str}")
                
                # Get schedule data
                schedule_data = self.get_channel_schedule(channel_name, date_str, date_str)
                
                if schedule_data:
                    # Save the data
                    self.save_schedule_data(channel_name, schedule_data)
                    
                    # Be nice to the API
                    time.sleep(1)
                else:
                    print(f"  No data available for {channel_name} on {date_str}")

def main():
    crawler = CTVCrawler()
    crawler.crawl_schedules(days_back=5)  # Crawl data for the last 3 days plus today

if __name__ == "__main__":
    main()