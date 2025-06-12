import requests
import json
import time
from datetime import datetime, timedelta
import urllib.parse
import logging

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s',
    handlers=[
        logging.FileHandler("ctv_crawler.log"),
        logging.StreamHandler()
    ]
)
logger = logging.getLogger()

class CTVCrawler:
    def __init__(self):
        self.base_url = "https://www.ctv.ca"
        self.capi_base_url = "https://capi.9c9media.com"
        self.graphql_url = f"{self.base_url}/space-graphql/apq/graphql"
        
        # Common headers
        self.common_headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "sec-ch-ua-platform": "Linux",
            "sec-ch-ua": "\"Not.A/Brand\";v=\"99\", \"Chromium\";v=\"136\"",
            "sec-ch-ua-mobile": "?0"
        }
        
        # API keys and secrets
        self.api_keys = None
        
        # Channel mapping
        self.channel_mapping = {}
        
    def get_smart_id(self):
        """Get API keys needed for subsequent API calls"""
        url = f"{self.base_url}/api/smart-id"
        headers = {
            **self.common_headers,
            "referer": f"{self.base_url}/on-air?tab=schedule"
        }
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            self.api_keys = response.json()
            logger.info("Successfully retrieved API keys")
            return self.api_keys
        except Exception as e:
            logger.error(f"Error getting smart ID: {e}")
            return None
    
    def get_site_navigation(self):
        """Retrieve the site navigation structure"""
        variables = {
            "subscriptions": ["CTV", "CTV_COMEDY", "CTV_DRAMA", "CTV_LIFE", "CTV_SCIFI", 
                             "CTV_MUCH", "E_NOW", "CTV_MOVIES", "CTV_THROWBACK", 
                             "USA", "OXYGEN", "WILD", "NATURE", "SPEED"],
            "maturity": "ADULT",
            "language": "ENGLISH",
            "authenticationState": "UNAUTH",
            "playbackLanguage": "ENGLISH"
        }
        
        extensions = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "aa5d37bc9e275d07e613518be1b270a87221f0ada7d4bc7d2d3f03bf06d881f6"
            }
        }
        
        params = {
            "operationName": "site",
            "variables": json.dumps(variables),
            "extensions": json.dumps(extensions)
        }
        
        headers = {
            **self.common_headers,
            "referer": f"{self.base_url}/on-air?tab=schedule",
            "content-type": "application/json",
            "graphql-client-platform": "entpay_web"
        }
        
        try:
            response = requests.get(self.graphql_url, params=params, headers=headers)
            response.raise_for_status()
            logger.info("Successfully retrieved site navigation")
            return response.json()
        except Exception as e:
            logger.error(f"Error getting site navigation: {e}")
            return None
    
    def get_channel_collections(self, postal_code="M5V"):
        """Retrieve a list of available channels and their identifiers"""
        url = f"{self.capi_base_url}/destinations/ctv_hub/platforms/atexace/collections/4126/contents"
        params = {
            "$include": "[Id,Tags,Media.Id]",
            "ContentPackages.Constraints.Geo.PostalCode": postal_code
        }
        
        headers = {
            **self.common_headers,
            "referer": f"{self.base_url}/"
        }
        
        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            # Process channel data
            channels = []
            for item in data.get("Items", []):
                channel_id = item.get("Id")
                channel_name = item.get("Name")
                media_id = item.get("Media", {}).get("Id")
                tags = item.get("Tags", [])
                
                if tags and len(tags) > 0:
                    channel_code = tags[0].get("Name")
                    
                    # Extract hub from channel name
                    hub = "ctv_hub"  # Default hub
                    if "CTV Wild" in channel_name:
                        hub = "ctvwild_hub"
                    elif "CTV Nature" in channel_name:
                        hub = "ctvnature_hub"
                    elif "CTV Speed" in channel_name:
                        hub = "ctvspeed_hub"
                    elif "CTV Much" in channel_name:
                        hub = "ctvmuch_hub"
                    elif "E!" in channel_name:
                        hub = "e_hub"
                    elif "CTV Drama" in channel_name:
                        hub = "ctvdrama_hub"
                    elif "CTV Sci-Fi" in channel_name:
                        hub = "ctvscifi_hub"
                    elif "CTV Comedy" in channel_name:
                        hub = "ctvcomedy_hub"
                    elif "Oxygen" in channel_name:
                        hub = "oxygen_hub"
                    elif "USA Network" in channel_name:
                        hub = "usa_hub"
                    elif "CTV Life" in channel_name:
                        hub = "ctvlife_hub"
                    
                    channels.append({
                        "id": channel_id,
                        "name": channel_name,
                        "media_id": media_id,
                        "channel_code": channel_code,
                        "hub": hub
                    })
                    
                    # Update channel mapping
                    self.channel_mapping[channel_name] = {
                        "hub": hub,
                        "channel_code": channel_code
                    }
            
            logger.info(f"Successfully retrieved {len(channels)} channels")
            return channels
        except Exception as e:
            logger.error(f"Error getting channel collections: {e}")
            return []
    
    def get_channel_schedule(self, hub, channel_code, start_date, end_date, timezone="-04:00"):
        """Retrieve TV listings for a specific channel for a given date range"""
        start_time = f"{start_date}T00:00:00{timezone}"
        end_time = f"{end_date}T23:59:59{timezone}"
        
        url = f"{self.capi_base_url}/destinations/{hub}/platforms/atexace/channelaffiliates/{channel_code}/schedules"
        params = {
            "StartTime": start_time,
            "EndTime": end_time,
            "$include": "[details]"
        }
        
        headers = {
            **self.common_headers,
            "referer": f"{self.base_url}/",
            "accept": "application/json"
        }
        
        try:
            response = requests.get(url, params=params, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            listings = data.get("Items", [])
            logger.info(f"Successfully retrieved {len(listings)} TV listings for {channel_code} from {start_date} to {end_date}")
            return listings
        except Exception as e:
            logger.error(f"Error getting channel schedule for {channel_code}: {e}")
            return []
    
    def get_schedule_data_graphql(self, content_id):
        """Retrieve TV schedule information for a specific channel using GraphQL"""
        variables = {
            "id": f"contentid/{content_id}"
        }
        
        extensions = {
            "persistedQuery": {
                "version": 1,
                "sha256Hash": "08f8b2df31d1cc0617c23b3a3af2e0f2056e8c76ebb23967c085b52ef25dfa5e"
            }
        }
        
        params = {
            "operationName": "schedule",
            "variables": json.dumps(variables),
            "extensions": json.dumps(extensions)
        }
        
        headers = {
            **self.common_headers,
            "referer": f"{self.base_url}/on-air?tab=schedule",
            "content-type": "application/json",
            "graphql-client-platform": "entpay_web"
        }
        
        try:
            response = requests.get(self.graphql_url, params=params, headers=headers)
            response.raise_for_status()
            logger.info(f"Successfully retrieved schedule data for content ID {content_id}")
            return response.json()
        except Exception as e:
            logger.error(f"Error getting schedule data for content ID {content_id}: {e}")
            return None
    
    def crawl_tv_schedules(self, days=7, timezone="-04:00"):
        """Crawl TV schedules for all channels for a specified number of days"""
        # Step 1: Initialize API access
        self.get_smart_id()
        
        # Step 2: Get channel information
        channels = self.get_channel_collections()
        
        # Step 3: Extract TV listings by channel
        all_schedules = {}
        
        # Generate date range
        today = datetime.now().date()
        date_range = [(today + timedelta(days=i)).strftime("%Y-%m-%d") for i in range(days)]
        
        for channel in channels:
            channel_name = channel["name"]
            hub = channel["hub"]
            channel_code = channel["channel_code"]
            
            logger.info(f"Processing channel: {channel_name} ({channel_code})")
            
            channel_schedules = []
            for start_date in date_range:
                # Add a small delay to avoid rate limiting
                time.sleep(0.5)
                
                # Get schedule for this date
                listings = self.get_channel_schedule(hub, channel_code, start_date, start_date, timezone)
                if listings:
                    channel_schedules.extend(listings)
            
            all_schedules[channel_name] = channel_schedules
            
            # Save data incrementally to avoid data loss in case of failure
            self.save_data(all_schedules, f"ctv_schedules_partial_{len(all_schedules)}.json")
        
        # Save complete data
        self.save_data(all_schedules, "ctv_schedules_complete.json")
        return all_schedules
    
    def save_data(self, data, filename):
        """Save data to a JSON file"""
        try:
            with open(filename, 'w', encoding='utf-8') as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Data saved to {filename}")
        except Exception as e:
            logger.error(f"Error saving data to {filename}: {e}")

def main():
    crawler = CTVCrawler()
    schedules = crawler.crawl_tv_schedules(days=7)
    logger.info(f"Crawling completed. Retrieved schedules for {len(schedules)} channels.")

if __name__ == "__main__":
    main()
    