#!/usr/bin/env python3
"""
Hotstar API Crawler

This script crawls the Hotstar API to extract content in a structured manner
and saves it in a hierarchical folder-file format.

Usage:
    python hotstar_crawler.py

Requirements:
    - requests
    - json
    - os
    - time
    - tqdm
"""

import requests
import json
import os
import time
import random
from tqdm import tqdm
from urllib.parse import urlparse, parse_qs
import dotenv

dotenv.load_dotenv()

class HotstarCrawler:
    def __init__(self, user_token=os.getenv('x-hs-usertoken'), device_id=os.getenv('x-hs-device-id')):
        """
        Initialize the Hotstar crawler with authentication details.
        
        Args:
            user_token (str): User token for authentication
            device_id (str): Device ID for authentication
        """
        self.base_url = "https://www.hotstar.com"
        self.api_base = f"{self.base_url}/api/internal/bff/v2"
        self.country = "in"  # Default country code
        self.result_dir = "../result_json"
        
        # Create result directory if it doesn't exist
        if not os.path.exists(self.result_dir):
            os.makedirs(self.result_dir)
        
        # Authentication details
        self.user_token = user_token or ""
        self.device_id = device_id or self._generate_device_id()
        
        # Common headers for all requests
        self.headers = {
            "x-request-id": self._generate_request_id(),
            "x-hs-client": "platform:web;app_version:25.03.06.1;browser:Chrome;schema_version:0.0.1429;os:Linux;os_version:x86_64;browser_version:136;network_data:4g",
            "x-hs-platform": "web",
            "x-country-code": self.country,
            "x-hs-accept-language": "eng",
            "x-hs-device-id": self.device_id,
            "x-hs-app": "250306001",
            "x-hs-usertoken": self.user_token
        }
        
        # Client capabilities for video requests
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
        
        # DRM parameters for video requests
        self.drm_parameters = {
            "hdcp_version": ["HDCP_V2_2"],
            "widevine_security_level": [],
            "playready_security_level": []
        }
    
    def _generate_device_id(self):
        """Generate a random device ID."""
        parts = []
        for _ in range(5):
            parts.append(''.join(random.choices('0123456789abcdef', k=6)))
        return '-'.join(parts)
    
    def _generate_request_id(self):
        """Generate a random request ID."""
        parts = []
        for length in [6, 6, 6, 6]:
            parts.append(''.join(random.choices('0123456789abcdef', k=length)))
        return '-'.join(parts)
    
    def _make_request(self, url, params=None):
        """
        Make a GET request to the API.
        
        Args:
            url (str): URL to request
            params (dict): Query parameters
            
        Returns:
            dict: JSON response
        """
        # Update request ID for each request
        self.headers["x-request-id"] = self._generate_request_id()
        self.headers["x-hs-request-id"] = self.headers["x-request-id"]
        
        try:
            response = requests.get(url, headers=self.headers, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"Request error: {e}")
            if hasattr(e, 'response') and e.response:
                print(f"Response status: {e.response.status_code}")
                print(f"Response body: {e.response.text[:200]}...")
            return None
    
    def get_home_page(self):
        """
        Get the homepage content.
        
        Returns:
            dict: Homepage content
        """
        url = f"{self.api_base}/slugs/{self.country}/home"
        return self._make_request(url)
    
    def get_content_details(self, content_type, content_slug, content_id):
        """
        Get details for a specific content item.
        
        Args:
            content_type (str): Type of content (shows, movies)
            content_slug (str): URL-friendly name of the content
            content_id (str): Unique identifier for the content
            
        Returns:
            dict: Content details
        """
        url = f"{self.api_base}/slugs/{self.country}/{content_type}/{content_slug}/{content_id}"
        return self._make_request(url)
    
    def get_tray_content(self, category, subcategory, tray_id, card_type="VERTICAL_LARGE"):
        """
        Get content items for a specific tray.
        
        Args:
            category (str): Content category
            subcategory (str): Content subcategory
            tray_id (str): Identifier for the tray
            card_type (str): Type of card layout
            
        Returns:
            dict: Tray content
        """
        url = f"{self.api_base}/slugs/{self.country}/browse/{category}/{subcategory}/{tray_id}"
        params = {"card_type": card_type}
        return self._make_request(url, params)
    
    def get_paginated_content(self, page_id, space_id, offset=0, size=10, page_enum="home", rws=None):
        """
        Get paginated content for a specific space.
        
        Args:
            page_id (str): Page identifier
            space_id (str): Space identifier
            offset (int): Starting position for content items
            size (int): Number of items to return
            page_enum (str): Page type
            rws (list): List of widget IDs to exclude
            
        Returns:
            dict: Paginated content
        """
        url = f"{self.api_base}/pages/{page_id}/spaces/{space_id}"
        params = {
            "offset": offset,
            "size": size,
            "page_enum": page_enum
        }
        
        if rws:
            params["rws"] = ",".join(rws)
        
        # Generate a random anchor-session-token
        timestamp = int(time.time() * 1000)
        random_suffix = ''.join(random.choices('abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789_-', k=16))
        params["anchor-session-token"] = f"{timestamp}-{random_suffix}"
        
        return self._make_request(url, params)
    
    def get_widget_items(self, url):
        """
        Get additional content items for a specific widget.
        
        Args:
            url (str): URL for fetching widget items
            
        Returns:
            dict: Widget items
        """
        full_url = f"{self.base_url}{url}"
        return self._make_request(full_url)
    
    def get_video_details(self, content_id):
        """
        Get video streaming details for a content item.
        
        Args:
            content_id (str): Content ID
            
        Returns:
            dict: Video details
        """
        url = f"{self.api_base}/pages/666/spaces/334/widgets/244"
        params = {
            "content_id": content_id,
            "client_capabilities": json.dumps(self.client_capabilities),
            "drm_parameters": json.dumps(self.drm_parameters)
        }
        return self._make_request(url, params)
    
    def extract_content_from_tray(self, tray_data):
        """
        Extract content items from a tray.
        
        Args:
            tray_data (dict): Tray data
            
        Returns:
            list: List of content items
        """
        content_items = []
        
        if not tray_data or "success" not in tray_data:
            return content_items
        
        # Extract items from grid widget
        try:
            widget_wrappers = tray_data["success"]["page"]["spaces"]["content"]["widget_wrappers"]
            for wrapper in widget_wrappers:
                if "widget" in wrapper and "data" in wrapper["widget"]:
                    if "items" in wrapper["widget"]["data"]:
                        content_items.extend(wrapper["widget"]["data"]["items"])
        except (KeyError, TypeError):
            pass
        
        return content_items
    
    def extract_content_from_home(self, home_data):
        """
        Extract content items from the homepage.
        
        Args:
            home_data (dict): Homepage data
            
        Returns:
            list: List of content items
        """
        content_items = []
        
        if not home_data or "success" not in home_data:
            return content_items
        
        # Extract items from content space
        try:
            widget_wrappers = home_data["success"]["page"]["spaces"]["content"]["widget_wrappers"]
            for wrapper in widget_wrappers:
                if "widget" in wrapper and "data" in wrapper["widget"]:
                    if "items" in wrapper["widget"]["data"]:
                        content_items.extend(wrapper["widget"]["data"]["items"])
        except (KeyError, TypeError):
            pass
        
        return content_items
    
    def extract_show_details(self, show_data):
        """
        Extract show details including seasons and episodes.
        
        Args:
            show_data (dict): Show data
            
        Returns:
            dict: Show details
        """
        if not show_data or "success" not in show_data:
            return {}
        
        show_details = {}
        
        try:
            # Extract show metadata from hero space
            hero_widget = show_data["success"]["page"]["spaces"]["hero"]["widget_wrappers"][0]["widget"]
            show_details = hero_widget["data"]
            
            # Clean up and structure the data
            structured_data = {
                "id": show_details.get("content_id", ""),
                "title": show_details.get("title", ""),
                "description": show_details.get("description", ""),
                "genre": show_details.get("genre", []),
                "language": show_details.get("lang", []),
                "seasons": []
            }
            
            # Extract seasons and episodes
            if "seasons" in show_details:
                for season in show_details["seasons"]:
                    season_data = {
                        "season_number": season.get("season_num", 0),
                        "episodes": []
                    }
                    
                    if "episodes" in season:
                        for episode in season["episodes"]:
                            episode_data = {
                                "id": episode.get("content_id", ""),
                                "title": episode.get("title", ""),
                                "description": episode.get("description", ""),
                                "episode_number": episode.get("episode_num", 0),
                                "duration": episode.get("duration", 0)
                            }
                            season_data["episodes"].append(episode_data)
                    
                    structured_data["seasons"].append(season_data)
            
            return structured_data
        
        except (KeyError, TypeError, IndexError) as e:
            print(f"Error extracting show details: {e}")
            return {}
    
    def extract_movie_details(self, movie_data):
        """
        Extract movie details.
        
        Args:
            movie_data (dict): Movie data
            
        Returns:
            dict: Movie details
        """
        if not movie_data or "success" not in movie_data:
            return {}
        
        try:
            # Extract movie metadata from hero space
            hero_widget = movie_data["success"]["page"]["spaces"]["hero"]["widget_wrappers"][0]["widget"]
            movie_details = hero_widget["data"]
            
            # Clean up and structure the data
            structured_data = {
                "id": movie_details.get("content_id", ""),
                "title": movie_details.get("title", ""),
                "description": movie_details.get("description", ""),
                "genre": movie_details.get("genre", []),
                "language": movie_details.get("lang", []),
                "duration": movie_details.get("duration", 0)
            }
            
            return structured_data
        
        except (KeyError, TypeError, IndexError) as e:
            print(f"Error extracting movie details: {e}")
            return {}
    
    def save_content(self, content_type, content_data, filename):
        """
        Save content data to a file.
        
        Args:
            content_type (str): Type of content (shows, movies)
            content_data (dict): Content data
            filename (str): Filename to save the data
        """
        # Create directory if it doesn't exist
        directory = os.path.join(self.result_dir, content_type)
        if not os.path.exists(directory):
            os.makedirs(directory)
        
        # Save data to file
        filepath = os.path.join(directory, filename)
        with open(filepath, 'w', encoding='utf-8') as f:
            json.dump(content_data, f, indent=2, ensure_ascii=False)
    
    def crawl_show(self, show_id, show_slug):
        """
        Crawl a TV show and its episodes.
        
        Args:
            show_id (str): Show ID
            show_slug (str): Show slug
            
        Returns:
            dict: Show details
        """
        print(f"Crawling show: {show_slug} ({show_id})")
        
        # Get show details
        show_data = self.get_content_details("shows", show_slug, show_id)
        show_details = self.extract_show_details(show_data)
        
        if not show_details:
            print(f"Failed to extract details for show: {show_slug}")
            return None
        
        # Create show directory
        show_dir = os.path.join(self.result_dir, "shows", show_slug)
        if not os.path.exists(show_dir):
            os.makedirs(show_dir)
        
        # Save show metadata
        show_metadata_path = os.path.join(show_dir, "metadata.json")
        with open(show_metadata_path, 'w', encoding='utf-8') as f:
            json.dump(show_details, f, indent=2, ensure_ascii=False)
        
        # Process each season and episode
        for season in show_details.get("seasons", []):
            season_num = season.get("season_number", 0)
            
            # Create season directory
            season_dir = os.path.join(show_dir, f"season_{season_num}")
            if not os.path.exists(season_dir):
                os.makedirs(season_dir)
            
            # Process episodes
            for episode in season.get("episodes", []):
                episode_num = episode.get("episode_number", 0)
                episode_id = episode.get("id", "")
                
                # Get video details for the episode
                if episode_id:
                    video_data = self.get_video_details(episode_id)
                    if video_data and "success" in video_data:
                        try:
                            # Extract streaming URL
                            media_asset = video_data["success"]["widget_wrapper"]["widget"]["data"]["media_asset"]
                            if "primary" in media_asset and "content_url" in media_asset["primary"]:
                                episode["streaming_url"] = media_asset["primary"]["content_url"]
                        except (KeyError, TypeError):
                            pass
                
                # Save episode data
                episode_filename = f"episode_{episode_num}.json"
                episode_path = os.path.join(season_dir, episode_filename)
                with open(episode_path, 'w', encoding='utf-8') as f:
                    json.dump(episode, f, indent=2, ensure_ascii=False)
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.5)
        
        return show_details
    
    def crawl_movie(self, movie_id, movie_slug):
        """
        Crawl a movie.
        
        Args:
            movie_id (str): Movie ID
            movie_slug (str): Movie slug
            
        Returns:
            dict: Movie details
        """
        print(f"Crawling movie: {movie_slug} ({movie_id})")
        
        # Get movie details
        movie_data = self.get_content_details("movies", movie_slug, movie_id)
        movie_details = self.extract_movie_details(movie_data)
        
        if not movie_details:
            print(f"Failed to extract details for movie: {movie_slug}")
            return None
        
        # Get video details for the movie
        video_data = self.get_video_details(movie_id)
        if video_data and "success" in video_data:
            try:
                # Extract streaming URL
                media_asset = video_data["success"]["widget_wrapper"]["widget"]["data"]["media_asset"]
                if "primary" in media_asset and "content_url" in media_asset["primary"]:
                    movie_details["streaming_url"] = media_asset["primary"]["content_url"]
            except (KeyError, TypeError):
                pass
        
        # Save movie data
        self.save_content("movies", movie_details, f"{movie_slug}.json")
        
        return movie_details
    
    def process_content_item(self, item):
        """
        Process a content item and determine its type.
        
        Args:
            item (dict): Content item
            
        Returns:
            tuple: (content_type, content_id, content_slug)
        """
        content_id = item.get("id", "")
        content_type = item.get("contentType", "").lower()
        
        # Extract slug from action URL
        content_slug = ""
        try:
            if "actions" in item and "on_click" in item["actions"]:
                for action in item["actions"]["on_click"]:
                    if "page_navigation" in action and "page_slug" in action["page_navigation"]:
                        slug_path = action["page_navigation"]["page_slug"]
                        parts = slug_path.split("/")
                        if len(parts) >= 3:
                            content_slug = parts[-1]
                            break
        except (KeyError, TypeError, IndexError):
            pass
        
        # If slug is not found, generate one from title
        if not content_slug and "title" in item:
            content_slug = item["title"].lower().replace(" ", "-")
        
        return content_type, content_id, content_slug
    
    def crawl_tray(self, category, subcategory, tray_id):
        """
        Crawl a content tray.
        
        Args:
            category (str): Content category
            subcategory (str): Content subcategory
            tray_id (str): Tray ID
            
        Returns:
            list: List of content items
        """
        print(f"Crawling tray: {category}/{subcategory}/{tray_id}")
        
        # Get initial tray content
        tray_data = self.get_tray_content(category, subcategory, tray_id)
        content_items = self.extract_content_from_tray(tray_data)
        
        # Handle pagination if available
        try:
            more_url = tray_data["success"]["page"]["spaces"]["content"]["widget_wrappers"][0]["widget"]["data"]["more_grid_items_url"]
            while more_url:
                # Extract query parameters
                parsed_url = urlparse(more_url)
                query_params = parse_qs(parsed_url.query)
                
                # Make request for more items
                more_data = self.get_widget_items(more_url)
                
                if not more_data or "success" not in more_data:
                    break
                
                # Extract items
                more_items = []
                try:
                    more_items = more_data["success"]["widget_wrapper"]["widget"]["data"]["items"]
                except (KeyError, TypeError):
                    pass
                
                if not more_items:
                    break
                
                # Add items to the list
                content_items.extend(more_items)
                
                # Check if there are more items
                try:
                    more_url = more_data["success"]["widget_wrapper"]["widget"]["data"]["more_grid_items_url"]
                except (KeyError, TypeError):
                    more_url = None
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.5)
        
        except (KeyError, TypeError):
            pass
        
        return content_items
    
    def crawl_home_page(self):
        """
        Crawl the homepage to discover content.
        
        Returns:
            tuple: (shows, movies) - Lists of show and movie IDs
        """
        print("Crawling homepage...")
        
        # Get homepage content
        home_data = self.get_home_page()
        content_items = self.extract_content_from_home(home_data)
        
        # Handle pagination for homepage content
        try:
            spaces = home_data["success"]["page"]["spaces"]
            content_space = spaces["content"]
            
            # Extract page and space IDs for pagination
            page_id = home_data["success"]["page"]["id"]
            space_id = content_space["id"]
            
            # Get widget IDs that have already been retrieved
            rws = []
            for wrapper in content_space.get("widget_wrappers", []):
                if "widget" in wrapper and "widget_commons" in wrapper["widget"]:
                    widget_id = wrapper["widget"]["widget_commons"].get("id", "")
                    if widget_id:
                        rws.append(widget_id)
            
            # Paginate through content
            offset = len(content_items)
            size = 10
            
            while True:
                more_data = self.get_paginated_content(page_id, space_id, offset, size, "home", rws)
                
                if not more_data or "success" not in more_data:
                    break
                
                # Extract items
                more_items = []
                try:
                    for wrapper in more_data["success"]["space"]["widget_wrappers"]:
                        if "widget" in wrapper and "data" in wrapper["widget"]:
                            if "items" in wrapper["widget"]["data"]:
                                more_items.extend(wrapper["widget"]["data"]["items"])
                            
                            # Add widget ID to rws
                            if "widget_commons" in wrapper["widget"]:
                                widget_id = wrapper["widget"]["widget_commons"].get("id", "")
                                if widget_id:
                                    rws.append(widget_id)
                except (KeyError, TypeError):
                    pass
                
                if not more_items:
                    break
                
                # Add items to the list
                content_items.extend(more_items)
                
                # Update offset for next page
                offset += size
                
                # Add a small delay to avoid rate limiting
                time.sleep(0.5)
        
        except (KeyError, TypeError) as e:
            print(f"Error during homepage pagination: {e}")
        
        # Process content items
        shows = []
        movies = []
        
        for item in content_items:
            content_type, content_id, content_slug = self.process_content_item(item)
            
            if content_id and content_slug:
                if content_type == "show":
                    shows.append((content_id, content_slug))
                elif content_type == "movie":
                    movies.append((content_id, content_slug))
        
        return shows, movies
    
    def crawl(self, max_shows=10, max_movies=10):
        """
        Main crawling function.
        
        Args:
            max_shows (int): Maximum number of shows to crawl
            max_movies (int): Maximum number of movies to crawl
        """
        print(f"Starting Hotstar crawler (max_shows={max_shows}, max_movies={max_movies})...")
        
        # Crawl homepage to discover content
        shows, movies = self.crawl_home_page()
        
        # Deduplicate content
        shows = list(set(shows))
        movies = list(set(movies))
        
        print(f"Discovered {len(shows)} shows and {len(movies)} movies")
        
        # Limit the number of items to crawl
        shows = shows[:max_shows]
        movies = movies[:max_movies]
        
        # Crawl shows
        print(f"\nCrawling {len(shows)} shows...")
        for i, (show_id, show_slug) in enumerate(tqdm(shows)):
            self.crawl_show(show_id, show_slug)
            # Add a delay between shows to avoid rate limiting
            if i < len(shows) - 1:
                time.sleep(1)
        
        # Crawl movies
        print(f"\nCrawling {len(movies)} movies...")
        for i, (movie_id, movie_slug) in enumerate(tqdm(movies)):
            self.crawl_movie(movie_id, movie_slug)
            # Add a delay between movies to avoid rate limiting
            if i < len(movies) - 1:
                time.sleep(1)
        
        print("\nCrawling completed!")


def main():
    """Main function to run the crawler."""
    # Get user token and device ID from command line arguments or environment variables
    import argparse
    
    parser = argparse.ArgumentParser(description='Hotstar API Crawler')
    parser.add_argument('--user-token', help='User token for authentication')
    parser.add_argument('--device-id', help='Device ID for authentication')
    parser.add_argument('--max-shows', type=int, default=10, help='Maximum number of shows to crawl')
    parser.add_argument('--max-movies', type=int, default=10, help='Maximum number of movies to crawl')
    
    args = parser.parse_args()
    
    # Initialize crawler
    crawler = HotstarCrawler(
        user_token=args.user_token,
        device_id=args.device_id
    )
    
    # Start crawling
    crawler.crawl(max_shows=args.max_shows, max_movies=args.max_movies)


if __name__ == "__main__":
    main()