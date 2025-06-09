import os
import json
import time
import requests
import logging
from urllib.parse import urljoin, urlparse, parse_qs
from pathlib import Path

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

class HotstarCrawler:
    def __init__(self, user_token, device_id):
        self.base_url = "https://www.hotstar.com"
        self.results_dir = Path("../results_claude3.7/hotstar")
        self.results_dir.mkdir(parents=True, exist_ok=True)
        
        self.user_token = user_token
        self.device_id = device_id
        self.country_code = "in"
        self.processed_urls = set()
        self.processed_content_ids = set()
        self.processed_tray_ids = set()
        
        self.headers = {
            "x-request-id": "40c987-5dd65d-4981ab-4072a8",
            "x-hs-client": "platform:web;app_version:25.03.06.1;browser:Chrome;schema_version:0.0.1429;os:Linux;os_version:x86_64;browser_version:136;network_data:4g",
            "x-hs-platform": "web",
            "x-country-code": self.country_code,
            "x-hs-accept-language": "eng",
            "x-hs-device-id": self.device_id,
            "x-hs-app": "250306001",
            "x-hs-request-id": "40c987-5dd65d-4981ab-4072a8",
            "x-hs-usertoken": self.user_token,
        }
        
        self.client_capabilities = {
            "ads": ["non_ssai"],
            "audio_channel": ["stereo"],
            "container": ["fmp4", "fmp4br", "ts"],
            "dvr": ["short"],
            "dynamic_range": ["sdr"],
            "encryption": ["plain"],
            "ladder": ["web", "tv", "phone"],
            "package": ["dash", "hls"],
            "resolution": ["sd", "hd", "fhd"],
            "video_codec": ["h264"],
            "video_codec_non_secure": ["h264"]
        }
        
        self.drm_parameters = {
            "hdcp_version": ["HDCP_V2_2"],
            "widevine_security_level": [],
            "playready_security_level": []
        }

    def make_request(self, url, params=None):
        """Make a GET request to the API with proper error handling and rate limiting"""
        if url in self.processed_urls:
            logger.info(f"Skipping already processed URL: {url}")
            return None
        
        self.processed_urls.add(url)
        
        # Add base URL if it's a relative URL
        if not url.startswith("http"):
            url = urljoin(self.base_url, url)
        
        try:
            logger.info(f"Making request to: {url}")
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            
            # Rate limiting
            time.sleep(1)
            
            return response.json()
        except requests.exceptions.RequestException as e:
            logger.error(f"Request failed: {e}")
            return None
        except json.JSONDecodeError:
            logger.error(f"Failed to decode JSON from response")
            return None

    def save_json(self, data, filename):
        """Save data as JSON file"""
        filepath = self.results_dir / filename
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved data to {filepath}")

    def crawl_home(self):
        """Crawl the homepage to get the main content structure"""
        url = f"/api/internal/bff/v2/slugs/{self.country_code}/home"
        data = self.make_request(url)
        
        if not data:
            logger.error("Failed to fetch homepage data")
            return
        
        self.save_json(data, "homepage.json")
        
        # Process content trays from homepage
        if 'success' in data and 'page' in data['success'] and 'spaces' in data['success']['page']:
            spaces = data['success']['page']['spaces']
            
            # Process content space
            if 'content' in spaces and 'widget_wrappers' in spaces['content']:
                for widget_wrapper in spaces['content']['widget_wrappers']:
                    self.process_widget_wrapper(widget_wrapper)

    def process_widget_wrapper(self, widget_wrapper):
        """Process a widget wrapper to extract content information"""
        if 'widget' not in widget_wrapper:
            return
        
        widget = widget_wrapper['widget']
        widget_type = widget.get('@type', '').split('.')[-1] if '@type' in widget else ''
        
        # Process different widget types
        if widget_type == 'ScrollableTrayWidget' and 'data' in widget and 'items' in widget['data']:
            self.process_tray_items(widget['data'])
            
            # Check for tray ID to fetch more details
            if 'title' in widget['data']:
                tray_title = widget['data']['title']
                tray_id = self.extract_tray_id_from_widget(widget)
                if tray_id and tray_id not in self.processed_tray_ids:
                    self.processed_tray_ids.add(tray_id)
                    self.crawl_tray(tray_id, tray_title)
        
        elif widget_type == 'GridWidget' and 'data' in widget and 'items' in widget['data']:
            self.process_tray_items(widget['data'])
            
            # Handle pagination for grid widgets
            if 'more_grid_items_url' in widget['data']:
                self.process_grid_pagination(widget['data']['more_grid_items_url'])
        
        # Process other widget types as needed
        elif widget_type in ['HeroGECWidget', 'AutoplayWidget'] and 'data' in widget:
            if 'content_id' in widget['data']:
                content_id = widget['data']['content_id']
                self.crawl_content_details(content_id)
            elif 'media_asset' in widget['data'] and 'primary' in widget['data']['media_asset']:
                # Extract content URL if available
                content_url = widget['data']['media_asset']['primary'].get('content_url')
                if content_url:
                    self.save_json({'content_url': content_url}, f"media_asset_{int(time.time())}.json")

    def extract_tray_id_from_widget(self, widget):
        """Extract tray ID from widget data"""
        if 'widget_commons' in widget and 'instrumentation' in widget['widget_commons']:
            instrumentation = widget['widget_commons']['instrumentation']
            if 'instrumentation_context_v2' in instrumentation and 'value' in instrumentation['instrumentation_context_v2']:
                context_value = instrumentation['instrumentation_context_v2']['value']
                # Try to extract tray_id from the context value
                if 'tp-' in context_value:
                    parts = context_value.split('tp-')
                    if len(parts) > 1:
                        tray_part = parts[1].split('_')[0]
                        return f"tp-{tray_part}"
        return None

    def process_tray_items(self, data):
        """Process items in a content tray"""
        if 'items' not in data:
            return
        
        for item in data['items']:
            if 'content_id' in item:
                content_id = item['content_id']
                if content_id not in self.processed_content_ids:
                    self.processed_content_ids.add(content_id)
                    self.crawl_content_details(content_id)

    def process_grid_pagination(self, pagination_url):
        """Process pagination for grid widgets"""
        if not pagination_url or pagination_url in self.processed_urls:
            return
        
        data = self.make_request(pagination_url)
        if not data:
            return
        
        # Save pagination data
        parsed_url = urlparse(pagination_url)
        query_params = parse_qs(parsed_url.query)
        tray_id = query_params.get('tray_id', ['unknown'])[0]
        self.save_json(data, f"grid_pagination_{tray_id}_{int(time.time())}.json")
        
        # Process widget wrapper from pagination response
        if 'success' in data and 'widget_wrapper' in data['success']:
            self.process_widget_wrapper(data['success']['widget_wrapper'])

    def crawl_tray(self, tray_id, tray_title):
        """Crawl a specific content tray"""
        # Construct a URL for the tray based on tray_id
        # This is an approximation as the exact category/subcategory might vary
        url = f"/api/internal/bff/v2/slugs/{self.country_code}/browse/reco-editorial/all/{tray_id}?card_type=VERTICAL_LARGE"
        
        data = self.make_request(url)
        if not data:
            return
        
        self.save_json(data, f"tray_{tray_id}.json")
        
        # Process content from the tray
        if 'success' in data and 'page' in data['success'] and 'spaces' in data['success']['page']:
            spaces = data['success']['page']['spaces']
            if 'content' in spaces and 'widget_wrappers' in spaces['content']:
                for widget_wrapper in spaces['content']['widget_wrappers']:
                    self.process_widget_wrapper(widget_wrapper)

    def crawl_content_details(self, content_id):
        """Crawl details for a specific content item"""
        # First try to get content type and slug
        content_type = "shows"  # Default to shows, but we'll try to determine the actual type
        
        # Try different content types
        for type_guess in ["shows", "movies", "sports"]:
            url = f"/api/internal/bff/v2/slugs/{self.country_code}/{type_guess}/content/{content_id}"
            data = self.make_request(url)
            
            if data and 'success' in data:
                content_type = type_guess
                self.save_json(data, f"content_{content_id}.json")
                
                # Process content details
                self.process_content_details(data, content_id)
                
                # Get streaming information
                self.get_streaming_info(content_id)
                
                break

    def process_content_details(self, data, content_id):
        """Process details of a content item"""
        if 'success' not in data or 'page' not in data['success'] or 'spaces' not in data['success']['page']:
            return
        
        spaces = data['success']['page']['spaces']
        
        # Process hero space which typically contains content metadata
        if 'hero' in spaces and 'widget_wrappers' in spaces['hero']:
            for widget_wrapper in spaces['hero']['widget_wrappers']:
                self.process_widget_wrapper(widget_wrapper)
        
        # Process related content if available
        if 'related' in spaces and 'widget_wrappers' in spaces['related']:
            for widget_wrapper in spaces['related']['widget_wrappers']:
                self.process_widget_wrapper(widget_wrapper)
        
        # Process seasons and episodes for TV shows
        if 'seasons' in spaces and 'widget_wrappers' in spaces['seasons']:
            for widget_wrapper in spaces['seasons']['widget_wrappers']:
                if 'widget' in widget_wrapper and 'data' in widget_wrapper['widget']:
                    widget_data = widget_wrapper['widget']['data']
                    if 'seasons' in widget_data:
                        for season in widget_data['seasons']:
                            if 'episodes' in season:
                                for episode in season['episodes']:
                                    if 'content_id' in episode:
                                        episode_id = episode['content_id']
                                        if episode_id not in self.processed_content_ids:
                                            self.processed_content_ids.add(episode_id)
                                            self.get_streaming_info(episode_id)

    def get_streaming_info(self, content_id):
        """Get streaming information for a content item"""
        url = "/api/internal/bff/v2/pages/666/spaces/334/widgets/244"
        params = {
            "content_id": content_id,
            "client_capabilities": json.dumps(self.client_capabilities),
            "drm_parameters": json.dumps(self.drm_parameters)
        }
        
        data = self.make_request(url, params)
        if not data:
            return
        
        self.save_json(data, f"streaming_{content_id}.json")
        
        # Extract video metadata URL if available
        if 'success' in data and 'widget_wrapper' in data['success'] and 'widget' in data['success']['widget_wrapper']:
            widget = data['success']['widget_wrapper']['widget']
            if 'data' in widget and 'media_asset' in widget['data'] and 'primary' in widget['data']['media_asset']:
                content_url = widget['data']['media_asset']['primary'].get('content_url')
                if content_url:
                    # Try to get video metadata
                    parsed_url = urlparse(content_url)
                    path_parts = parsed_url.path.split('/')
                    if len(path_parts) >= 7:
                        # Construct video-meta.json URL
                        base_path = '/'.join(path_parts[:-1])
                        video_meta_url = f"{parsed_url.scheme}://{parsed_url.netloc}{base_path}/video-meta.json"
                        
                        # Make request without using make_request to avoid adding to processed_urls
                        try:
                            response = requests.get(video_meta_url, headers={"referer": self.base_url})
                            if response.status_code == 200:
                                video_meta = response.json()
                                self.save_json(video_meta, f"video_meta_{content_id}.json")
                        except Exception as e:
                            logger.error(f"Failed to fetch video metadata: {e}")

    def crawl_spaces(self, page_id, space_id, offset=0, size=10):
        """Crawl spaces with pagination support"""
        url = f"/api/internal/bff/v2/pages/{page_id}/spaces/{space_id}"
        params = {
            "anchor-session-token": f"{int(time.time() * 1000)}-{self.device_id[:10]}",
            "offset": offset,
            "page_enum": "home",
            "size": size
        }
        
        data = self.make_request(url, params)
        if not data:
            return
        
        self.save_json(data, f"space_{page_id}_{space_id}_offset_{offset}.json")
        
        # Process widget wrappers
        if 'success' in data and 'space' in data['success'] and 'widget_wrappers' in data['success']['space']:
            for widget_wrapper in data['success']['space']['widget_wrappers']:
                self.process_widget_wrapper(widget_wrapper)
            
            # Paginate if there are likely more items
            if len(data['success']['space']['widget_wrappers']) >= size:
                self.crawl_spaces(page_id, space_id, offset + size, size)

    def run(self):
        """Run the crawler"""
        logger.info("Starting Hotstar crawler")
        
        # Start with the homepage
        self.crawl_home()
        
        # Crawl some common spaces
        self.crawl_spaces("2169", "8451")
        
        logger.info(f"Crawling completed. Processed {len(self.processed_urls)} URLs and {len(self.processed_content_ids)} content items.")

if __name__ == "__main__":
    # User token and device ID from the provided documentation
    USER_TOKEN = "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IiIsImF1ZCI6InVtX2FjY2VzcyIsImV4cCI6MTc0OTUzMzY4MSwiaWF0IjoxNzQ5NDQ3MjgxLCJpc3MiOiJUUyIsImp0aSI6IjlhOTEzMTc1OGI4ODQ5MTE4MjBmMjgzOGI1OTVmNTBlIiwic3ViIjoie1wiaElkXCI6XCJjMWIyMDk5MzVmMzM0MDU3ODZmNWRlYzFlZTA4NmRkYlwiLFwicElkXCI6XCIyODY0NGJhOWNlZWU0MGVhOTMzODgzMjhkMTc5ZTNkZlwiLFwiZHdIaWRcIjpcImVkNTc2YTA2ZDFjZDY1Y2I3NTgwNTk3NzM4YzBlMDI0ZGE4N2U0NWQ2NTk1MTBhODM1OGI4OGFhNmQ4ZDdlYzBcIixcImR3UGlkXCI6XCJhOGM0Y2E0ZTU5M2NhYjNlZmNkZGY0ZjgyM2U4OTdlM2NlMjYxYjg4ODE4ZDE5Y2ZjMWZiYzNmOTk4OTlhY2FkXCIsXCJvbGRIaWRcIjpcImMxYjIwOTkzNWYzMzQwNTc4NmY1ZGVjMWVlMDg2ZGRiXCIsXCJvbGRQaWRcIjpcIjI4NjQ0YmE5Y2VlZTQwZWE5MzM4ODMyOGQxNzllM2RmXCIsXCJpc1BpaVVzZXJNaWdyYXRlZFwiOmZhbHNlLFwibmFtZVwiOlwiWW91XCIsXCJpcFwiOlwiMjAzLjE5OS41Ny45OFwiLFwiY291bnRyeUNvZGVcIjpcImluXCIsXCJjdXN0b21lclR5cGVcIjpcIm51XCIsXCJ0eXBlXCI6XCJndWVzdFwiLFwiaXNFbWFpbFZlcmlmaWVkXCI6ZmFsc2UsXCJpc1Bob25lVmVyaWZpZWRcIjpmYWxzZSxcImRldmljZUlkXCI6XCI3NTM5OWEtN2FmOTNjLTQ1OWY3ZS0yMDU3ZGZcIixcInByb2ZpbGVcIjpcIkFEVUxUXCIsXCJ2ZXJzaW9uXCI6XCJ2MlwiLFwic3Vic2NyaXB0aW9uc1wiOntcImluXCI6e319LFwiaXNzdWVkQXRcIjoxNzQ5NDQ3MjgxMTM2LFwibWF0dXJpdHlMZXZlbFwiOlwiQVwiLFwiZHBpZFwiOlwiMjg2NDRiYTljZWVlNDBlYTkzMzg4MzI4ZDE3OWUzZGZcIixcInN0XCI6MSxcImRhdGFcIjpcIkNnUUlBQklBQ2dRSUFDb0FDZ3dJQUNJSWtBR1FtTmZMOURJS0JBZ0FPZ0FLQkFnQU1nQUtCQWdBUWdBPVwifSIsInZlcnNpb24iOiIxXzAifQ.Tpm9Xb6v0iQOCvHz31kmSXlhWjOIZ5nxMWwnobcpKCM"
    DEVICE_ID = "75399a-7af93c-459f7e-2057df"
    
    crawler = HotstarCrawler(USER_TOKEN, DEVICE_ID)
    crawler.run()
    