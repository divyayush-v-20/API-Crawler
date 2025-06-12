#!/usr/bin/env python3
"""
CTV Schedule Crawler

This script crawls the CTV API to extract TV schedule data and stores it in a structured format.
"""

import os
import json
import time
import datetime
import requests
from urllib.parse import quote

class CTVCrawler:
    def __init__(self):
        self.base_url = "https://www.ctv.ca"
        self.capi_url = "https://capi.9c9media.com"
        self.graphql_url = f"{self.base_url}/space-graphql/apq/graphql"
        self.output_dir = "../result_json"
        self.headers = {
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36",
            "Accept": "application/json",
            "sec-ch-ua-platform": "Linux",
            "sec-ch-ua": "\"Not.A/Brand\";v=\"99\", \"Chromium\";v=\"136\"",
            "sec-ch-ua-mobile": "?0",
            "referer": "https://www.ctv.ca/on-air?tab=schedule"
        }
        self.api_keys = None
        self.channel_mapping = None
        
        # Create output directory if it doesn't exist
        os.makedirs(self.output_dir, exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "shows"), exist_ok=True)
        os.makedirs(os.path.join(self.output_dir, "movies"), exist_ok=True)

    def get_smart_id(self):
        """Get API keys needed for authentication"""
        url = f"{self.base_url}/api/smart-id"
        response = requests.get(url, headers=self.headers)
        if response.status_code == 200:
            self.api_keys = response.json()
            print(f"Successfully retrieved API keys: {self.api_keys}")
            return self.api_keys
        else:
            print(f"Failed to get API keys: {response.status_code}")
            return None

    def get_channel_collections(self, postal_code="M5V"):
        """Get list of available channels and their identifiers"""
        url = f"{self.capi_url}/destinations/ctv_hub/platforms/atexace/collections/4126/contents"
        params = {
            "$include": "[Id,Tags,Media.Id,Name]",
            "ContentPackages.Constraints.Geo.PostalCode": postal_code
        }
        
        response = requests.get(url, params=params, headers=self.headers)
        if response.status_code == 200:
            channels = response.json()
            # Create a mapping of channel names to their codes and hubs
            self.channel_mapping = self._create_channel_mapping(channels)
            return self.channel_mapping
        else:
            print(f"Failed to get channel collections: {response.status_code}")
            return None

    def _create_channel_mapping(self, channels_data):
        """Create a mapping of channel names to their codes and hubs"""
        # Predefined mapping of channel names to hubs
        hub_mapping = {
            "CTV Wild": "ctvwild_hub",
            "CTV Nature": "ctvnature_hub",
            "CTV Speed": "ctvspeed_hub",
            "CTV Much": "ctvmuch_hub",
            "E!": "e_hub",
            "CTV Drama": "ctvdrama_hub",
            "CTV Sci-Fi": "ctvscifi_hub",
            "CTV Comedy": "ctvcomedy_hub",
            "Oxygen": "oxygen_hub",
            "USA Network": "usa_hub",
            "CTV Life": "ctvlife_hub"
        }
        
        channel_mapping = {}
        for item in channels_data.get("Items", []):
            name = item.get("Name")
            if not name:
                continue
                
            # Get the channel code from Tags
            channel_code = None
            for tag in item.get("Tags", []):
                if tag.get("Name"):
                    channel_code = tag.get("Name")
                    break
            
            if not channel_code:
                continue
                
            # Determine the hub based on the channel name
            hub = "ctv_hub"  # Default hub for CTV regional channels
            for prefix, specific_hub in hub_mapping.items():
                if name.startswith(prefix):
                    hub = specific_hub
                    break
                    
            channel_mapping[name] = {
                "code": channel_code,
                "hub": hub,
                "id": item.get("Id")
            }
            
        return channel_mapping

    def get_channel_schedule(self, channel_name, start_date=None, end_date=None):
        """Get TV schedule for a specific channel and date range"""
        if not self.channel_mapping:
            self.get_channel_collections()
            
        if channel_name not in self.channel_mapping:
            print(f"Channel {channel_name} not found in mapping")
            return None
            
        channel_info = self.channel_mapping[channel_name]
        channel_hub = channel_info["hub"]
        channel_code = channel_info["code"]
        
        # Default to today if no dates provided
        if not start_date:
            start_date = datetime.datetime.now()
        if not end_date:
            end_date = start_date + datetime.timedelta(days=1)
            
        # Format dates for API
        start_time = start_date.strftime("%Y-%m-%dT00:00:00-04:00")
        end_time = end_date.strftime("%Y-%m-%dT23:59:59-04:00")
        
        url = f"{self.capi_url}/destinations/{channel_hub}/platforms/atexace/channelaffiliates/{channel_code}/schedules"
        params = {
            "StartTime": start_time,
            "EndTime": end_time,
            "$include": "[details]"
        }
        
        headers = self.headers.copy()
        headers["referer"] = "https://www.ctv.ca/"
        
        response = requests.get(url, params=params, headers=headers)
        if response.status_code == 200:
            schedule_data = response.json()
            return schedule_data
        else:
            print(f"Failed to get schedule for {channel_name}: {response.status_code}")
            return None

    def process_schedule_data(self, schedule_data):
        """Process schedule data and organize by content type"""
        if not schedule_data or "Items" not in schedule_data:
            return None
            
        shows = {}
        movies = {}
        
        for item in schedule_data["Items"]:
            entity_type = item.get("EntityType", "")
            sub_type = item.get("SubType", "")
            
            # Process TV shows
            if entity_type == "Episode" and sub_type == "Series":
                show_name = item.get("Name", "Unknown Show")
                
                if show_name not in shows:
                    shows[show_name] = {
                        "episodes": [],
                        "genres": item.get("Genres", []),
                        "description": item.get("LongDescription", item.get("Desc", ""))
                    }
                
                episode = {
                    "title": item.get("Title", "Untitled Episode"),
                    "description": item.get("Desc", ""),
                    "season": item.get("SeasonNo"),
                    "episode": item.get("EpisodeNumber"),
                    "air_time": item.get("StartTime"),
                    "duration": item.get("Duration"),
                    "release_year": item.get("ReleaseYear"),
                    "images": item.get("Images", []),
                    "cast": item.get("TopCast", []),
                    "directors": item.get("Directors", [])
                }
                
                shows[show_name]["episodes"].append(episode)
                
            # Process movies
            elif entity_type == "Movie" or (entity_type == "Episode" and sub_type == "Feature Film"):
                movie_name = item.get("Name", "Unknown Movie")
                
                if movie_name not in movies:
                    movies[movie_name] = {
                        "title": movie_name,
                        "description": item.get("LongDescription", item.get("Desc", "")),
                        "air_time": item.get("StartTime"),
                        "duration": item.get("Duration"),
                        "release_year": item.get("ReleaseYear"),
                        "genres": item.get("Genres", []),
                        "images": item.get("Images", []),
                        "cast": item.get("TopCast", []),
                        "directors": item.get("Directors", [])
                    }
        
        return {"shows": shows, "movies": movies}

    def save_content(self, content_data):
        """Save content data to files in a hierarchical structure"""
        if not content_data:
            return
            
        # Save shows
        shows_dir = os.path.join(self.output_dir, "shows")
        for show_name, show_data in content_data.get("shows", {}).items():
            # Create a safe filename
            safe_name = "".join([c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in show_name])
            safe_name = safe_name.strip().replace(' ', '_')
            
            # Create show directory
            show_dir = os.path.join(shows_dir, safe_name)
            os.makedirs(show_dir, exist_ok=True)
            
            # Save show info
            with open(os.path.join(show_dir, "info.json"), 'w') as f:
                json.dump({
                    "name": show_name,
                    "genres": show_data.get("genres", []),
                    "description": show_data.get("description", "")
                }, f, indent=2)
            
            # Save episodes
            for i, episode in enumerate(show_data.get("episodes", [])):
                episode_filename = f"s{episode.get('season', '00')}e{episode.get('episode', str(i+1).zfill(2))}.json"
                with open(os.path.join(show_dir, episode_filename), 'w') as f:
                    json.dump(episode, f, indent=2)
        
        # Save movies
        movies_dir = os.path.join(self.output_dir, "movies")
        for movie_name, movie_data in content_data.get("movies", {}).items():
            # Create a safe filename
            safe_name = "".join([c if c.isalnum() or c in [' ', '-', '_'] else '_' for c in movie_name])
            safe_name = safe_name.strip().replace(' ', '_')
            
            # Save movie info
            with open(os.path.join(movies_dir, f"{safe_name}.json"), 'w') as f:
                json.dump(movie_data, f, indent=2)

    def crawl_all_channels(self, days=7):
        """Crawl schedules for all channels for a specified number of days"""
        if not self.channel_mapping:
            self.get_channel_collections()
            
        if not self.channel_mapping:
            print("Failed to get channel mapping. Exiting.")
            return
            
        today = datetime.datetime.now()
        
        for channel_name, channel_info in self.channel_mapping.items():
            print(f"Crawling schedule for {channel_name}...")
            
            for day_offset in range(days):
                current_date = today + datetime.timedelta(days=day_offset)
                print(f"  Getting schedule for {current_date.strftime('%Y-%m-%d')}...")
                
                schedule_data = self.get_channel_schedule(
                    channel_name, 
                    start_date=current_date,
                    end_date=current_date
                )
                
                if schedule_data:
                    content_data = self.process_schedule_data(schedule_data)
                    self.save_content(content_data)
                    print(f"  Saved {len(content_data.get('shows', {}))} shows and {len(content_data.get('movies', {}))} movies")
                
                # Be nice to the API
                time.sleep(1)
            
            # Be extra nice between channels
            time.sleep(2)

    def run(self):
        """Main execution method"""
        print("Starting CTV Schedule Crawler...")
        
        # Get API keys
        self.get_smart_id()
        
        # Get channel information
        self.get_channel_collections()
        
        # Crawl all channels for the next 7 days
        self.crawl_all_channels(days=7)
        
        print(f"Crawling complete! Results saved to {self.output_dir}")


if __name__ == "__main__":
    crawler = CTVCrawler()
    crawler.run()