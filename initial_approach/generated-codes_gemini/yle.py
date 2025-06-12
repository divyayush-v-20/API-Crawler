import requests
import json
import re
from datetime import datetime, timedelta
import time

class YLEAreenaCrawler:
    """
    A crawler to extract TV schedule data from YLE Areena's APIs,
    based on the provided comprehensive documentation.
    """

    # Base URLs for the API and the website
    API_BASE_URL = "https://areena.api.yle.fi"
    WEB_BASE_URL = "https://areena.yle.fi"

    # Common parameters and headers from documentation
    BASE_PARAMS = {
        'language': 'fi',
        'v': '10',
        'client': 'yle-areena-web',
        'country': 'FI', # Default to FI, can be updated by location API
        'app_id': 'areena-web-items',
        'app_key': 'wlTs5D9OjIdeS9krPzRQR4I1PYVzoazN'
    }
    
    COMMON_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'Referer': 'https://areena.yle.fi/'
    }

    # Channel IDs from documentation
    CHANNELS = [
        "yle-tv1",
        "yle-tv2",
        "yle-teema-fem",
        "tv-finland",
        "yle-areena"
    ]

    def __init__(self):
        """Initializes the crawler, sets up the session, and fetches the dynamic build_id."""
        self.session = requests.Session()
        self.session.headers.update(self.COMMON_HEADERS)
        self.session.cookies.set("yle_selva", "1749181611342597482")
        
        print("Step 1: Initial Setup...")
        self.build_id = self._fetch_build_id()
        if not self.build_id:
            raise RuntimeError("Could not fetch the dynamic build_id. Crawler cannot proceed.")
        print(f"Successfully fetched dynamic build_id: {self.build_id}")
        
        self.get_location() # Optional but recommended step from docs


    def _fetch_build_id(self):
        """
        Dynamically fetches the Next.js build_id from the TV guide page HTML.
        This is critical as it changes with site updates.
        """
        try:
            print("Fetching homepage to find build_id...")
            response = self.session.get(f"{self.WEB_BASE_URL}/tv/opas")
            response.raise_for_status()
            
            # Use regex to find the buildId from the __NEXT_DATA__ script tag
            match = re.search(r'"buildId":"([a-zA-Z0-9_-]+)"', response.text)
            if match:
                return match.group(1)
        except requests.exceptions.RequestException as e:
            print(f"Error fetching page to get build_id: {e}")
        return None

    def get_location(self):
        """
        API 3: Determines the user's geographic location.
        """
        print("Fetching user location...")
        url = "https://locations.api.yle.fi/v4/address/current"
        params = {
            'app_id': 'analytics-sdk',
            'app_key': 'RVaxtSmiGRRUDos7uAmOCh6fReH9SEyg'
        }
        try:
            response = self.session.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            country_code = data.get('country_code', 'FI')
            # Update base params with the detected country code
            self.BASE_PARAMS['country'] = country_code
            print(f"Location determined. Using country code: {country_code}")
            return data
        except requests.exceptions.RequestException as e:
            print(f"Could not fetch location data: {e}. Using default 'FI'.")
        return None

    def get_channel_schedule(self, channel_id, target_date):
        """
        API 1: Retrieves the full program schedule for a specific channel and date,
        handling pagination internally.
        """
        date_str = target_date.strftime('%Y-%m-%d')
        print(f"  - Fetching schedule for channel '{channel_id}' on {date_str}...")
        
        url = f"{self.API_BASE_URL}/v1/ui/schedules/{channel_id}/{date_str}.json"
        all_programs = []
        offset = 0
        limit = 100 # As per documentation default

        while True:
            params = self.BASE_PARAMS.copy()
            params.update({
                'yleReferer': f"tv.guide.{date_str}.tv_opas.{channel_id}.untitled_list",
                'offset': offset,
                'limit': limit
            })
            
            response = self.session.get(url, params=params)
            if not response or response.status_code != 200:
                print(f"    ! Failed to fetch data for offset {offset}.")
                break
                
            data = response.json()
            programs = data.get('data', [])
            all_programs.extend(programs)
            
            # Check pagination metadata
            meta = data.get('meta', {})
            total_count = meta.get('count', 0)
            
            if not programs or len(all_programs) >= total_count:
                break
            
            offset += limit

        print(f"    > Found {len(all_programs)} total programs.")
        return all_programs

    def crawl_schedules(self, start_date, num_days=1):
        """
        Executes the full content traversal strategy to get schedules.

        Args:
            start_date (datetime.date): The starting date for the schedule crawl.
            num_days (int): The number of consecutive days to crawl.

        Returns:
            dict: A dictionary containing schedule data, organized by channel and date.
        """
        print("\n--- Starting YLE Areena Schedule Crawl ---")
        
        final_schedules = {}
        date_range = [start_date + timedelta(days=i) for i in range(num_days)]

        # 2. Date Discovery (generating programmatically as it's more reliable)
        # 3. Channel Iteration
        for target_date in date_range:
            for channel_id in self.CHANNELS:
                if channel_id not in final_schedules:
                    final_schedules[channel_id] = {}
                
                date_str = target_date.strftime('%Y-%m-%d')
                
                # 4. Schedule Retrieval & 5. Pagination Handling
                programs = self.get_channel_schedule(channel_id, target_date)
                
                # 6. Data Processing
                processed_programs = []
                for prog in programs:
                    start_time, end_time = None, None
                    for label in prog.get('labels', []):
                        if label.get('type') == 'broadcastStartDate':
                            start_time = label.get('raw')
                        elif label.get('type') == 'broadcastEndDate':
                            end_time = label.get('raw')
                    
                    processed_programs.append({
                        'title': prog.get('title'),
                        'description': prog.get('description'),
                        'startTime': start_time,
                        'endTime': end_time,
                        'program_id_uri': prog.get('pointer', {}).get('uri')
                    })
                
                final_schedules[channel_id][date_str] = processed_programs
                time.sleep(0.5) # Be a good internet citizen

        print("\n--- YLE Areena Schedule Crawl Complete ---")
        return final_schedules


if __name__ == '__main__':
    try:
        # Initialize the crawler. This will automatically handle setup steps.
        crawler = YLEAreenaCrawler()
    except RuntimeError as e:
        print(f"Error initializing crawler: {e}")
    else:
        # Define the date range for the crawl
        # Let's get the schedule for today and the next day.
        crawl_start_date = datetime.now().date()
        days_to_crawl = 2

        print(f"\nCrawler will fetch schedules from {crawl_start_date.strftime('%Y-%m-%d')} for {days_to_crawl} days.")

        # Run the crawler
        crawled_data = crawler.crawl_schedules(start_date=crawl_start_date, num_days=days_to_crawl)

        # Print the final compiled data
        print("\n" + "="*50)
        print("CRAWLING COMPLETE. GATHERED DATA:")
        print("="*50)
        
        if crawled_data:
            # Save to a file for easier inspection
            output_filename = "../results/yle_areena_schedule.json"
            with open(output_filename, "w", encoding="utf-8") as f:
                json.dump(crawled_data, f, indent=2, ensure_ascii=False)
            print(f"Successfully saved all schedule data to '{output_filename}'")
        else:
            print("No data was crawled. Please check the script and API status.")