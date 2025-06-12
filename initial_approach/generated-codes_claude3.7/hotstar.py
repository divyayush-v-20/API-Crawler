import requests
import json
import os
import time
import logging
from urllib.parse import urljoin, urlparse, parse_qs
import random

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')
logger = logging.getLogger(__name__)

class HotstarCrawler:
    def __init__(self):
        self.base_url = "https://www.hotstar.com"
        self.api_base_url = "https://www.hotstar.com/api/internal/bff/v2"
        self.headers = {
            "x-request-id": self._generate_request_id(),
            "x-hs-client": "platform:web;app_version:25.03.06.1;browser:Chrome;schema_version:0.0.1429;os:Linux;os_version:x86_64;browser_version:136;network_data:4g",
            "x-hs-platform": "web",
            "x-country-code": "in",
            "x-hs-accept-language": "eng",
            "x-hs-device-id": "3623b1-20d753-3cc29c-11bb32",
            "x-hs-app": "250306001",
            "x-hs-usertoken": "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJhcHBJZCI6IiIsImF1ZCI6InVtX2FjY2VzcyIsImV4cCI6MTc0OTU1MzQ1MSwiaWF0IjoxNzQ5NDY3MDUxLCJpc3MiOiJUUyIsImp0aSI6IjhmMWJhOTNmNTMxYjRmOTJhOWJiODNlNDE3MzRmNmFlIiwic3ViIjoie1wiaElkXCI6XCJlZmRlM2IzYjA1Nzg0MGE3ODIzNDdmZWNkYTE5YjM5N1wiLFwicElkXCI6XCJmODJjNWM4MjhmOTQ0ZDdkOTgzMjI4MjFiNDFlYjRmZFwiLFwiZHdIaWRcIjpcIjdiODVhZWE1NzI0NTNkMjJkMTVkZWFiOGVkODA5OWY5N2Y2MmI4YzE2ZWZmYTQwMDQ1YzEwOGM3NGQ3YjI4NGRcIixcImR3UGlkXCI6XCI0MjY4MTEwYjc2NjA4ZTIxZTA0OTRlMzQxZGFhMDg5MjE2ZmRjNDc4ZGM5NTQ0NTg4OWUwNmU5MTIxYjg2ZGViXCIsXCJvbGRIaWRcIjpcImVmZGUzYjNiMDU3ODQwYTc4MjM0N2ZlY2RhMTliMzk3XCIsXCJvbGRQaWRcIjpcImY4MmM1YzgyOGY5NDRkN2Q5ODMyMjgyMWI0MWViNGZkXCIsXCJpc1BpaVVzZXJNaWdyYXRlZFwiOmZhbHNlLFwibmFtZVwiOlwiWW91XCIsXCJpcFwiOlwiMjAzLjE5OS41Ny45OFwiLFwiY291bnRyeUNvZGVcIjpcImluXCIsXCJjdXN0b21lclR5cGVcIjpcIm51XCIsXCJ0eXBlXCI6XCJndWVzdFwiLFwiaXNFbWFpbFZlcmlmaWVkXCI6ZmFsc2UsXCJpc1Bob25lVmVyaWZpZWRcIjpmYWxzZSxcImRldmljZUlkXCI6XCIzNjIzYjEtMjBkNzUzLTNjYzI5Yy0xMWJiMzJcIixcInByb2ZpbGVcIjpcIkFEVUxUXCIsXCJ2ZXJzaW9uXCI6XCJ2MlwiLFwic3Vic2NyaXB0aW9uc1wiOntcImluXCI6e319LFwiaXNzdWVkQXRcIjoxNzQ5NDY3MDUxNzkzLFwiZHBpZFwiOlwiZjgyYzVjODI4Zjk0NGQ3ZDk4MzIyODIxYjQxZWI0ZmRcIixcInN0XCI6MSxcImRhdGFcIjpcIkNnUUlBRElBQ2dRSUFDb0FDZ1FJQUJJQUNnUUlBRG9BQ2dRSUFFSUFDZ3dJQUNJSWtBSDk3ZktpOVRJPVwifSIsInZlcnNpb24iOiIxXzAifQ.CAIHUw9TelTQ1wn4aUz4Myahhkk5A9ihbC9r0qwuez0"
        }
        self.results_dir = "../results_claude3.7/hotstar"
        self.processed_content_ids = set()
        self.processed_trays = set()
        self.country = "in"
        
        # Create results directory if it doesn't exist
        os.makedirs(self.results_dir, exist_ok=True)
        
    def _generate_request_id(self):
        """Generate a random request ID in the format used by Hotstar"""
        parts = []
        for length in [6, 6, 6, 6]:
            part = ''.join(random.choice('0123456789abcdef') for _ in range(length))
            parts.append(part)
        return '-'.join(parts)
    
    def _update_request_headers(self):
        """Update request headers with a new request ID"""
        request_id = self._generate_request_id()
        self.headers["x-request-id"] = request_id
        self.headers["x-hs-request-id"] = request_id
        
    def make_request(self, url, params=None):
        """Make a request to the API with error handling and rate limiting"""
        self._update_request_headers()
        
        max_retries = 3
        retry_count = 0
        
        while retry_count < max_retries:
            try:
                response = requests.get(url, headers=self.headers, params=params)
                response.raise_for_status()
                return response.json()
            except requests.exceptions.RequestException as e:
                retry_count += 1
                wait_time = 2 ** retry_count  # Exponential backoff
                logger.error(f"Request failed: {e}. Retrying in {wait_time} seconds... (Attempt {retry_count}/{max_retries})")
                time.sleep(wait_time)
        
        logger.error(f"Failed to make request to {url} after {max_retries} attempts")
        return None
    
    def save_to_json(self, data, filename):
        """Save data to a JSON file"""
        filepath = os.path.join(self.results_dir, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
        logger.info(f"Saved data to {filepath}")
    
    def extract_content_from_widget(self, widget):
        """Extract content items from a widget"""
        content_items = []
        
        if not widget or "@type" not in widget:
            return content_items
        
        widget_type = widget.get("@type", "")
        
        if "ScrollableTrayWidget" in widget_type:
            items = widget.get("data", {}).get("items", [])
            for item in items:
                content_item = self._extract_content_item(item)
                if content_item:
                    content_items.append(content_item)
        
        elif "GridWidget" in widget_type:
            items = widget.get("data", {}).get("items", [])
            for item in items:
                content_item = self._extract_content_item(item)
                if content_item:
                    content_items.append(content_item)
        
        elif "HeroGECWidget" in widget_type:
            data = widget.get("data", {})
            content_item = {
                "content_id": data.get("content_id"),
                "title": data.get("title"),
                "description": data.get("description"),
                "content_type": data.get("content_type"),
                "genre": data.get("genre", []),
                "language": data.get("lang", []),
                "images": data.get("images", {})
            }
            
            # Add seasons and episodes if available
            if "seasons" in data:
                content_item["seasons"] = data.get("seasons", [])
            
            content_items.append(content_item)
        
        return content_items
    
    def _extract_content_item(self, item):
        """Extract content information from an item"""
        if not item:
            return None
        
        content_id = item.get("content_id")
        if not content_id:
            return None
        
        return {
            "content_id": content_id,
            "title": item.get("title"),
            "description": item.get("description", ""),
            "content_type": item.get("content_type", ""),
            "images": item.get("images", {}),
            "genre": item.get("genre", []),
            "language": item.get("lang", [])
        }
    
    def crawl_home(self):
        """Crawl the homepage to get initial content structure"""
        url = f"{self.api_base_url}/slugs/{self.country}/home"
        logger.info(f"Crawling homepage: {url}")
        
        response = self.make_request(url)
        if not response or "success" not in response:
            logger.error("Failed to get homepage data")
            return None
        
        # Save the homepage data
        self.save_to_json(response, "homepage.json")
        
        # Extract content from the homepage
        content_data = {"categories": []}
        
        # Extract navigation menu items (categories)
        try:
            spaces = response["success"]["page"]["spaces"]
            header_space = spaces.get("header", {})
            widget_wrappers = header_space.get("widget_wrappers", [])
            
            for wrapper in widget_wrappers:
                if "BrandedLogoHeaderWidget" in wrapper.get("template", ""):
                    widget = wrapper.get("widget", {})
                    data = widget.get("data", {})
                    nav_items = data.get("nav_items", [])
                    
                    for nav_item in nav_items:
                        if "title" in nav_item and "actions" in nav_item:
                            actions = nav_item.get("actions", {})
                            on_click = actions.get("on_click", [])
                            
                            for action in on_click:
                                if "page_navigation" in action:
                                    page_nav = action["page_navigation"]
                                    category = {
                                        "title": nav_item["title"],
                                        "page_slug": page_nav.get("page_slug", ""),
                                        "page_url": page_nav.get("page_url", "")
                                    }
                                    content_data["categories"].append(category)
        except Exception as e:
            logger.error(f"Error extracting navigation menu: {e}")
        
        # Extract content trays
        content_trays = []
        try:
            content_space = spaces.get("content", {})
            widget_wrappers = content_space.get("widget_wrappers", [])
            
            for wrapper in widget_wrappers:
                widget = wrapper.get("widget", {})
                if "@type" in widget and "ScrollableTrayWidget" in widget["@type"]:
                    tray_data = widget.get("data", {})
                    tray = {
                        "title": tray_data.get("title", ""),
                        "items": []
                    }
                    
                    items = tray_data.get("items", [])
                    for item in items:
                        content_item = self._extract_content_item(item)
                        if content_item:
                            tray["items"].append(content_item)
                    
                    content_trays.append(tray)
        except Exception as e:
            logger.error(f"Error extracting content trays: {e}")
        
        content_data["trays"] = content_trays
        self.save_to_json(content_data, "content_structure.json")
        
        # Process each content tray to get more details
        for tray in content_trays:
            self.process_tray_items(tray)
        
        # Process categories
        for category in content_data["categories"]:
            if category["page_slug"] and category["title"] != "Home":
                self.crawl_category(category)
        
        return content_data
    
    def crawl_category(self, category):
        """Crawl a specific category page"""
        page_slug = category["page_slug"]
        if not page_slug.startswith("/"):
            page_slug = f"/{page_slug}"
        
        # Extract category and subcategory from the slug
        parts = page_slug.strip("/").split("/")
        if len(parts) < 2:
            logger.warning(f"Invalid page slug format: {page_slug}")
            return
        
        category_name = parts[1]  # e.g., "movies", "shows", "sports"
        
        url = f"{self.api_base_url}/slugs/{self.country}/{category_name}"
        logger.info(f"Crawling category: {category_name}, URL: {url}")
        
        response = self.make_request(url)
        if not response or "success" not in response:
            logger.error(f"Failed to get data for category: {category_name}")
            return
        
        # Save the category data
        self.save_to_json(response, f"category_{category_name}.json")
        
        # Extract content trays from the category page
        content_trays = []
        try:
            spaces = response["success"]["page"]["spaces"]
            content_space = spaces.get("content", {})
            widget_wrappers = content_space.get("widget_wrappers", [])
            
            for wrapper in widget_wrappers:
                widget = wrapper.get("widget", {})
                if "@type" in widget and "ScrollableTrayWidget" in widget["@type"]:
                    tray_data = widget.get("data", {})
                    tray_id = tray_data.get("tray_id", "")
                    
                    if tray_id and tray_id not in self.processed_trays:
                        self.processed_trays.add(tray_id)
                        
                        tray = {
                            "title": tray_data.get("title", ""),
                            "tray_id": tray_id,
                            "items": []
                        }
                        
                        items = tray_data.get("items", [])
                        for item in items:
                            content_item = self._extract_content_item(item)
                            if content_item:
                                tray["items"].append(content_item)
                        
                        content_trays.append(tray)
                        
                        # Process the tray to get more details
                        self.process_tray_items(tray)
                        
                        # Crawl the tray details if it has a valid tray_id
                        if tray_id and "/" in tray_id:
                            self.crawl_tray_details(category_name, tray_id)
        except Exception as e:
            logger.error(f"Error extracting content trays from category {category_name}: {e}")
        
        category_content = {
            "category": category_name,
            "trays": content_trays
        }
        
        self.save_to_json(category_content, f"{category_name}_content.json")
    
    def crawl_tray_details(self, category, tray_id):
        """Crawl details for a specific tray"""
        # Parse the tray_id to extract necessary components
        parts = tray_id.split("_")
        if len(parts) < 2:
            logger.warning(f"Invalid tray_id format: {tray_id}")
            return
        
        tray_type = parts[0]
        tray_code = parts[1]
        
        # Determine subcategory based on tray_type
        subcategory_mapping = {
            "tp-ed": "editorial",
            "tp-reco": "recommended",
            "tp-genre": "genre"
        }
        
        subcategory = subcategory_mapping.get(tray_type, "general")
        
        url = f"{self.api_base_url}/slugs/{self.country}/browse/{category}/{subcategory}/{tray_id}?card_type=VERTICAL_LARGE"
        logger.info(f"Crawling tray details: {tray_id}, URL: {url}")
        
        response = self.make_request(url)
        if not response or "success" not in response:
            logger.error(f"Failed to get data for tray: {tray_id}")
            return
        
        # Save the tray details
        self.save_to_json(response, f"tray_{tray_id.replace('/', '_')}.json")
        
        # Extract content items from the tray
        content_items = []
        try:
            spaces = response["success"]["page"]["spaces"]
            content_space = spaces.get("content", {})
            widget_wrappers = content_space.get("widget_wrappers", [])
            
            for wrapper in widget_wrappers:
                widget = wrapper.get("widget", {})
                if "@type" in widget and "GridWidget" in widget["@type"]:
                    grid_data = widget.get("data", {})
                    items = grid_data.get("items", [])
                    
                    for item in items:
                        content_item = self._extract_content_item(item)
                        if content_item:
                            content_items.append(content_item)
                            
                            # Process the content item to get more details
                            self.process_content_item(content_item)
                    
                    # Handle pagination if more_grid_items_url is available
                    more_url = grid_data.get("more_grid_items_url")
                    if more_url:
                        self.process_pagination(more_url, tray_id)
        except Exception as e:
            logger.error(f"Error extracting content items from tray {tray_id}: {e}")
        
        tray_content = {
            "tray_id": tray_id,
            "category": category,
            "subcategory": subcategory,
            "items": content_items
        }
        
        self.save_to_json(tray_content, f"tray_content_{tray_id.replace('/', '_')}.json")
    
    def process_pagination(self, more_url, tray_id, depth=0):
        """Process pagination for grid items"""
        if depth > 5:  # Limit pagination depth to avoid infinite loops
            return
        
        # Construct the full URL
        if more_url.startswith("/"):
            more_url = f"{self.base_url}{more_url}"
        
        logger.info(f"Processing pagination: {more_url}")
        
        response = self.make_request(more_url)
        if not response or "success" not in response:
            logger.error(f"Failed to get pagination data for URL: {more_url}")
            return
        
        # Extract content items from the pagination response
        content_items = []
        try:
            widget_wrapper = response["success"]["widget_wrapper"]
            widget = widget_wrapper.get("widget", {})
            if "@type" in widget and "GridWidget" in widget["@type"]:
                grid_data = widget.get("data", {})
                items = grid_data.get("items", [])
                
                for item in items:
                    content_item = self._extract_content_item(item)
                    if content_item:
                        content_items.append(content_item)
                        
                        # Process the content item to get more details
                        self.process_content_item(content_item)
                
                # Handle further pagination
                more_url = grid_data.get("more_grid_items_url")
                if more_url:
                    self.process_pagination(more_url, tray_id, depth + 1)
        except Exception as e:
            logger.error(f"Error extracting content items from pagination: {e}")
        
        pagination_content = {
            "tray_id": tray_id,
            "page": depth + 1,
            "items": content_items
        }
        
        self.save_to_json(pagination_content, f"pagination_{tray_id.replace('/', '_')}_{depth + 1}.json")
    
    def process_tray_items(self, tray):
        """Process items in a content tray"""
        for item in tray.get("items", []):
            self.process_content_item(item)
    
    def process_content_item(self, content_item):
        """Process a content item to get more details"""
        content_id = content_item.get("content_id")
        content_type = content_item.get("content_type", "")
        
        if not content_id or content_id in self.processed_content_ids:
            return
        
        self.processed_content_ids.add(content_id)
        
        # Map content_type to API path
        content_type_mapping = {
            "MOVIE": "movies",
            "SHOW": "shows",
            "SPORT": "sports",
            "CHANNEL": "channels",
            "movie": "movies",
            "show": "shows",
            "sport": "sports",
            "channel": "channels"
        }
        
        api_content_type = content_type_mapping.get(content_type, "content")
        
        # Generate a slug from the title
        title = content_item.get("title", "")
        slug = title.lower().replace(" ", "-").replace(":", "").replace("'", "")
        
        url = f"{self.api_base_url}/slugs/{self.country}/{api_content_type}/{slug}/{content_id}"
        logger.info(f"Processing content item: {title} ({content_id}), URL: {url}")
        
        response = self.make_request(url)
        if not response or "success" not in response:
            logger.warning(f"Failed to get details for content: {content_id}")
            return
        
        # Save the content details
        self.save_to_json(response, f"content_{content_id}.json")
        
        # Extract detailed content information
        content_details = {}
        try:
            spaces = response["success"]["page"]["spaces"]
            hero_space = spaces.get("hero", {})
            widget_wrappers = hero_space.get("widget_wrappers", [])
            
            for wrapper in widget_wrappers:
                widget = wrapper.get("widget", {})
                content_items = self.extract_content_from_widget(widget)
                
                if content_items:
                    content_details = content_items[0]
                    
                    # If it's a show, process its seasons and episodes
                    if content_type.lower() == "show" and "seasons" in content_details:
                        self.process_show_seasons(content_details)
        except Exception as e:
            logger.error(f"Error extracting details for content {content_id}: {e}")
        
        self.save_to_json(content_details, f"details_{content_id}.json")
    
    def process_show_seasons(self, show_details):
        """Process seasons and episodes of a TV show"""
        content_id = show_details.get("content_id")
        seasons = show_details.get("seasons", [])
        
        for season in seasons:
            season_num = season.get("season_num")
            episodes = season.get("episodes", [])
            
            for episode in episodes:
                episode_id = episode.get("content_id")
                if episode_id and episode_id not in self.processed_content_ids:
                    self.processed_content_ids.add(episode_id)
                    
                    # Process the episode to get more details
                    episode_item = {
                        "content_id": episode_id,
                        "title": episode.get("title"),
                        "description": episode.get("description", ""),
                        "content_type": "episode",
                        "images": episode.get("images", {})
                    }
                    
                    self.process_content_item(episode_item)
        
        # Save the processed show with seasons and episodes
        show_content = {
            "content_id": content_id,
            "title": show_details.get("title"),
            "description": show_details.get("description"),
            "content_type": "show",
            "genre": show_details.get("genre", []),
            "language": show_details.get("language", []),
            "images": show_details.get("images", {}),
            "seasons": seasons
        }
        
        self.save_to_json(show_content, f"show_{content_id}.json")
    
    def crawl(self):
        """Main crawling function"""
        logger.info("Starting Hotstar crawler")
        
        # Start with the homepage
        home_data = self.crawl_home()
        
        logger.info("Crawling completed")
        return home_data

if __name__ == "__main__":
    crawler = HotstarCrawler()
    crawler.crawl()
