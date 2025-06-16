#!/usr/bin/env python3
import requests
import json
import os
import re
import time
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class YleAreenaCrawler:
    def __init__(self, days_to_crawl=7):
        self.days_to_crawl = days_to_crawl
        self.base_url = "https://areena.api.yle.fi"
        self.next_data_url = "https://areena.yle.fi/_next/data"
        self.location_url = "https://locations.api.yle.fi/v4/address/current"
        
        # Common API parameters
        self.common_params = {
            "language": "fi",
            "v": "10",
            "client": "yle-areena-web",
            "country": "IN",  # Will be updated with actual location
            "app_id": "areena-web-items",
            "app_key": "wlTs5D9OjIdeS9krPzRQR4I1PYVzoazN"
        }
        
        # Common headers
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
        self.channels = [
            "yle-tv1",
            "yle-tv2",
            "yle-teema-fem",
            "tv-finland",
            "yle-areena"
        ]
        
        # Create output directory
        self.output_dir = "yle_areena_results"
        os.makedirs(self.output_dir, exist_ok=True)
        
        # Get build_id and location
        self.build_id = self._get_build_id()
        self._get_location()

    def _get_build_id(self):
        """Extract the build_id from the main page"""
        try:
            response = requests.get("https://areena.yle.fi/tv/opas", headers=self.headers)
            response.raise_for_status()
            
            # Extract build_id from the HTML
            build_id_match = re.search(r'/_next/static/([^/]+)/_buildManifest\.js', response.text)
            if build_id_match:
                build_id = build_id_match.group(1)
                logger.info(f"Found build_id: {build_id}")
                return build_id
            else:
                logger.error("Could not find build_id in the page")
                return "Q_35nL8jUwGOhxPC9wVX5"  # Fallback to example build_id
        except Exception as e:
            logger.error(f"Error getting build_id: {e}")
            return "Q_35nL8jUwGOhxPC9wVX5"  # Fallback to example build_id

    def _get_location(self):
        """Get user location information"""
        try:
            params = {
                "app_id": "analytics-sdk",
                "app_key": "RVaxtSmiGRRUDos7uAmOCh6fReH9SEyg"
            }
            
            response = requests.get(
                self.location_url,
                params=params,
                headers=self.headers,
                cookies=self.cookies
            )
            response.raise_for_status()
            
            location_data = response.json()
            self.common_params["country"] = location_data.get("country_code", "IN")
            logger.info(f"Location set to: {self.common_params['country']}")
        except Exception as e:
            logger.error(f"Error getting location: {e}")
            # Keep default country code

    def _sanitize_filename(self, filename):
        """Sanitize filename by replacing spaces with underscores and removing special characters"""
        # Replace spaces with underscores
        sanitized = filename.replace(' ', '_')
        # Remove special characters
        sanitized = re.sub(r'[^\w\-.]', '', sanitized)
        return sanitized

    def get_tv_guide_dates(self):
        """Get available dates from the TV guide navigation API"""
        dates = []
        today = datetime.now()
        
        # Generate dates for the past n days including today
        for i in range(self.days_to_crawl):
            date = today - timedelta(days=i)
            dates.append(date.strftime("%Y-%m-%d"))
        
        return dates

    def get_channel_schedule(self, channel_id, date):
        """Get the TV program schedule for a specific channel on a specific date"""
        all_programs = []
        offset = 0
        limit = 100
        
        while True:
            try:
                # Construct the yleReferer parameter
                yle_referer = f"tv.guide.{date}.tv_opas.{channel_id}.untitled_list"
                
                # Set up parameters
                params = self.common_params.copy()
                params.update({
                    "yleReferer": yle_referer,
                    "offset": offset,
                    "limit": limit
                })
                
                # Make the request
                url = f"{self.base_url}/v1/ui/schedules/{channel_id}/{date}.json"
                response = requests.get(
                    url,
                    params=params,
                    headers=self.headers,
                    cookies=self.cookies
                )
                response.raise_for_status()
                
                data = response.json()
                programs = data.get("data", [])
                all_programs.extend(programs)
                
                # Check if we need to paginate
                meta = data.get("meta", {})
                total_count = meta.get("count", 0)
                
                if offset + limit >= total_count or not programs:
                    break
                
                offset += limit
                time.sleep(1)  # Be nice to the server
                
            except Exception as e:
                logger.error(f"Error getting schedule for {channel_id} on {date}: {e}")
                break
        
        return all_programs

    def save_program_data(self, program, channel_id, date):
        """Save program data to a JSON file"""
        try:
            # Extract program title
            title = program.get("title", "Unknown_Program")
            sanitized_title = self._sanitize_filename(title)
            
            # Extract program ID from pointer.uri if available
            program_id = "unknown_id"
            pointer = program.get("pointer", {})
            if pointer and "uri" in pointer:
                uri = pointer["uri"]
                id_match = re.search(r'yleareena://items/(\S+)', uri)
                if id_match:
                    program_id = id_match.group(1)
            
            # Create channel directory
            channel_dir = os.path.join(self.output_dir, channel_id)
            os.makedirs(channel_dir, exist_ok=True)
            
            # Create date directory
            date_dir = os.path.join(channel_dir, date)
            os.makedirs(date_dir, exist_ok=True)
            
            # Create filename with program ID for uniqueness
            filename = f"{sanitized_title}_{program_id}.json"
            filepath = os.path.join(date_dir, filename)
            
            # Add broadcast time information for better context
            broadcast_time = "unknown_time"
            for label in program.get("labels", []):
                if label.get("type") == "broadcastStartDate" and "raw" in label:
                    broadcast_time = label["raw"]
                    break
            
            # Add metadata to help with organization
            program_data = {
                "channel_id": channel_id,
                "broadcast_date": date,
                "broadcast_time": broadcast_time,
                "program_data": program
            }
            
            # Save to file
            with open(filepath, 'w', encoding='utf-8') as f:
                json.dump(program_data, f, ensure_ascii=False, indent=2)
            
            logger.debug(f"Saved program: {title} to {filepath}")
            
        except Exception as e:
            logger.error(f"Error saving program data: {e}")

    def crawl(self):
        """Main crawling function"""
        logger.info("Starting YLE Areena TV schedule crawler")
        
        # Get available dates
        dates = self.get_tv_guide_dates()
        logger.info(f"Crawling data for dates: {dates}")
        
        # Iterate through dates and channels
        for date in dates:
            logger.info(f"Processing date: {date}")
            
            for channel_id in self.channels:
                logger.info(f"Processing channel: {channel_id}")
                
                # Get channel schedule
                programs = self.get_channel_schedule(channel_id, date)
                logger.info(f"Found {len(programs)} programs for {channel_id} on {date}")
                
                # Save each program
                for program in programs:
                    self.save_program_data(program, channel_id, date)
                
                time.sleep(2)  # Be nice to the server
        
        logger.info("Crawling completed")

def main():
    # Create and run the crawler for the last 7 days (including today)
    crawler = YleAreenaCrawler(days_to_crawl=7)
    crawler.crawl()

if __name__ == "__main__":
    main()