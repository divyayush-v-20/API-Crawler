import requests
import json
from datetime import datetime, timedelta
import pytz # A robust library for timezone calculations
import time

class CTVCrawler:
    """
    A crawler to extract TV schedule data from CTV's APIs based on the
    provided comprehensive documentation.
    """

    # Base URLs from the documentation
    CAPI_BASE_URL = "https://capi.9c9media.com"
    CTV_BASE_URL = "https://www.ctv.ca"

    # Common headers required for most requests
    COMMON_HEADERS = {
        'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
        'Accept': 'application/json',
        'sec-ch-ua-platform': '"Linux"',
        'sec-ch-ua': '"Not.A/Brand";v="99", "Chromium";v="136"',
        'sec-ch-ua-mobile': '?0',
        'Referer': 'https://www.ctv.ca/'
    }

    # Channel mapping table provided in the documentation
    CHANNEL_MAPPING = [
        {'name': 'CTV Wild', 'hub': 'ctvwild_hub', 'code': 'WILD-G'},
        {'name': 'CTV Nature', 'hub': 'ctvnature_hub', 'code': 'NATURE-G'},
        {'name': 'CTV Speed', 'hub': 'ctvspeed_hub', 'code': 'SPEED-G'},
        {'name': 'CTV Much', 'hub': 'ctvmuch_hub', 'code': 'MUCHHD-G'},
        {'name': 'E!', 'hub': 'e_hub', 'code': 'ECANHD-G'},
        {'name': 'CTV Drama', 'hub': 'ctvdrama_hub', 'code': 'BRAVOC-G'},
        {'name': 'CTV Sci-Fi', 'hub': 'ctvscifi_hub', 'code': 'SPCECHD-G'},
        {'name': 'CTV Comedy', 'hub': 'ctvcomedy_hub', 'code': 'CMDY-G'},
        {'name': 'Oxygen', 'hub': 'oxygen_hub', 'code': 'OXYG-G'},
        {'name': 'USA Network', 'hub': 'usa_hub', 'code': 'USA-G'},
        {'name': 'CTV Life', 'hub': 'ctvlife_hub', 'code': 'LIFEH-G'},
        {'name': 'CTV Toronto', 'hub': 'ctv_hub', 'code': 'CFTO-G'},
        {'name': 'CTV Vancouver', 'hub': 'ctv_hub', 'code': 'CIVT-G'},
        {'name': 'CTV Calgary', 'hub': 'ctv_hub', 'code': 'CFCN-G'},
        {'name': 'CTV Edmonton', 'hub': 'ctv_hub', 'code': 'CFRN-G'},
        {'name': 'CTV Montreal', 'hub': 'ctv_hub', 'code': 'CFCF-G'},
        {'name': 'CTV Ottawa', 'hub': 'ctv_hub', 'code': 'CJOH-G'},
        {'name': 'CTV Winnipeg', 'hub': 'ctv_hub', 'code': 'CKY-G'}
    ]

    def __init__(self, timezone='America/Toronto'):
        """
        Initializes the crawler.

        Args:
            timezone (str): The timezone to use for generating StartTime and EndTime
                            query parameters. Defaults to 'America/Toronto'.
        """
        self.session = requests.Session()
        self.session.headers.update(self.COMMON_HEADERS)
        self.timezone = pytz.timezone(timezone)
        self.api_keys = {}

    def _make_request(self, method, url, **kwargs):
        """Helper method to make robust API requests."""
        try:
            response = self.session.request(method, url, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred for {url}: {http_err} - {response.text}")
        except requests.exceptions.RequestException as req_err:
            print(f"Request error occurred for {url}: {req_err}")
        except json.JSONDecodeError:
            print(f"Failed to decode JSON from response for {url}: {response.text}")
        return None

    def get_smart_id_keys(self):
        """
        API 1: Retrieves API keys needed for subsequent API calls.
        """
        print("Step 1: Fetching Smart ID API keys...")
        url = f"{self.CTV_BASE_URL}/api/smart-id"
        response = self._make_request("GET", url)
        if response:
            self.api_keys = response
            print("Successfully fetched API keys.")
            return self.api_keys
        print("Failed to fetch API keys.")
        return None

    def get_channel_schedule(self, channel_hub, channel_code, target_date):
        """
        API 4.2: Retrieves detailed TV listings for a specific channel and date.
        """
        # Format the date and time strings as required by the API
        start_of_day = self.timezone.localize(datetime.combine(target_date, datetime.min.time()))
        end_of_day = self.timezone.localize(datetime.combine(target_date, datetime.max.time()))

        # The API requires the format: YYYY-MM-DDTHH:MM:SSZ, where Z is the timezone offset
        start_time_str = start_of_day.isoformat()
        end_time_str = end_of_day.isoformat()

        url = (
            f"{self.CAPI_BASE_URL}/destinations/{channel_hub}/platforms/atexace/"
            f"channelaffiliates/{channel_code}/schedules"
        )
        
        params = {
            'StartTime': start_time_str,
            'EndTime': end_time_str,
            '$include': '[details]'
        }

        response = self._make_request("GET", url, params=params)
        return response.get("Items", []) if response else []

    def crawl_schedules(self, start_date, num_days=1):
        """
        Executes the full content traversal strategy to get schedules.

        Args:
            start_date (datetime.date): The starting date for the schedule crawl.
            num_days (int): The number of consecutive days to crawl.

        Returns:
            dict: A dictionary containing schedule data, organized by channel name.
        """
        print("--- Starting CTV Schedule Crawl ---")
        
        # 1. Initialize API Access (as per documentation)
        self.get_smart_id_keys()

        all_schedules = {}
        date_range = [start_date + timedelta(days=i) for i in range(num_days)]

        # 2. Get Channel Information (using the hardcoded mapping from documentation)
        print(f"\nStep 2: Using pre-defined list of {len(self.CHANNEL_MAPPING)} channels.")

        # 3. & 4. Extract and Process TV Listings by Channel and Date
        for channel in self.CHANNEL_MAPPING:
            channel_name = channel['name']
            print(f"\n--- Fetching schedules for: {channel_name} ---")
            all_schedules[channel_name] = []
            
            for target_date in date_range:
                date_str = target_date.strftime('%Y-%m-%d')
                print(f"  - Querying date: {date_str}")
                
                schedule_items = self.get_channel_schedule(
                    channel_hub=channel['hub'],
                    channel_code=channel['code'],
                    target_date=target_date
                )
                
                if schedule_items:
                    print(f"    > Found {len(schedule_items)} programs.")
                    all_schedules[channel_name].extend(schedule_items)
                else:
                    print("    > No schedule data returned.")
                
                # Be a good internet citizen; avoid overwhelming the server.
                time.sleep(0.5)

        print("\n--- CTV Schedule Crawl Complete ---")
        return all_schedules


if __name__ == '__main__':
    # Initialize the crawler. You can change the timezone if needed.
    crawler = CTVCrawler(timezone='America/Toronto')

    # Define the date range for the crawl
    # Let's get the schedule for today and the next 2 days.
    crawl_start_date = datetime.now().date()
    days_to_crawl = 3

    print(f"Crawler will fetch schedules from {crawl_start_date.strftime('%Y-%m-%d')} for {days_to_crawl} days.\n")

    # Run the crawler
    final_schedule_data = crawler.crawl_schedules(start_date=crawl_start_date, num_days=days_to_crawl)

    # Print the final compiled data
    print("\n" + "="*50)
    print("CRAWLING COMPLETE. GATHERED DATA:")
    print("="*50)
    
    if final_schedule_data:
        # Save to a file for easier inspection
        output_filename = "ctv_schedule.json"
        with open(output_filename, "w", encoding="utf-8") as f:
            json.dump(final_schedule_data, f, indent=2, ensure_ascii=False)
        print(f"Successfully saved all schedule data to '{output_filename}'")
    else:
        print("No data was crawled. Please check the script and API status.")