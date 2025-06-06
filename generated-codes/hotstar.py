import requests
import json
import urllib.parse
import uuid

class HotstarCrawler:
    """
    A crawler for Hotstar based on the provided API documentation.

    This class implements methods to interact with Hotstar's key API endpoints
    for content discovery, metadata retrieval, and fetching playback information.
    """

    BASE_URL = "https://www.hotstar.com"

    def __init__(self, user_token, device_id, country_code='in', language='eng'):
        """
        Initializes the crawler with necessary authentication and session details.

        Args:
            user_token (str): The x-hs-usertoken value for authenticated requests.
            device_id (str): The x-hs-device-id value.
            country_code (str): The two-letter country code (e.g., 'in').
            language (str): The desired language for content.
        """
        if not user_token or not device_id:
            raise ValueError("user_token and device_id are required.")

        self.country_code = country_code
        self.session = requests.Session()
        self.session.headers.update({
            "x-hs-client": "platform:web;app_version:25.03.06.1;browser:Chrome;schema_version:0.0.1429;os:Linux;os_version:x86_64;browser_version:136;network_data:4g",
            "x-hs-platform": "web",
            "x-country-code": self.country_code,
            "x-hs-accept-language": language,
            "x-hs-app": "250306001",
            "x-hs-usertoken": user_token,
            "x-hs-device-id": device_id,
            "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36"
        })

    def _make_request(self, method, url, **kwargs):
        """
        A helper method to make API requests with unique request IDs.
        """
        request_id = str(uuid.uuid4())
        headers = {
            "x-request-id": request_id,
            "x-hs-request-id": request_id
        }
        try:
            response = self.session.request(method, url, headers=headers, **kwargs)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.HTTPError as http_err:
            print(f"HTTP error occurred: {http_err} - {response.text}")
        except requests.exceptions.RequestException as req_err:
            print(f"Request error occurred: {req_err}")
        except json.JSONDecodeError:
            print(f"Failed to decode JSON from response: {response.text}")
        return None

    def get_home_page(self):
        """
        Endpoint 1: Retrieves the homepage structure and content.
        Corresponds to: GET /api/internal/bff/v2/slugs/{country}/home
        """
        print(f"Fetching homepage for country: {self.country_code}...")
        url = f"{self.BASE_URL}/api/internal/bff/v2/slugs/{self.country_code}/home"
        return self._make_request("GET", url)

    def get_tray_details(self, tray_url_path, card_type="VERTICAL_LARGE"):
        """
        Endpoint 3: Retrieves detailed content for a specific tray.
        Corresponds to: GET /api/internal/bff/v2/slugs/{country}/browse/{...}/{...}
        """
        print(f"Fetching tray details for: {tray_url_path}")
        url = f"{self.BASE_URL}{tray_url_path}?card_type={card_type}"
        return self._make_request("GET", url)

    def get_paginated_tray_items(self, more_url):
        """
        Endpoint 4: Retrieves additional content items for a widget (grid pagination).
        Corresponds to: GET /api/internal/bff/v2/pages/{...}/spaces/{...}/widgets/{...}/items
        """
        print(f"Fetching paginated items from: {more_url}")
        full_url = f"{self.BASE_URL}{more_url}"
        return self._make_request("GET", full_url)
        
    def get_content_details(self, content_slug):
        """
        Endpoint 5: Retrieves detailed information about a specific content item.
        Corresponds to: GET /api/internal/bff/v2/slugs/{country}/{...}/{...}/{...}
        """
        print(f"Fetching content details for: {content_slug}")
        url = f"{self.BASE_URL}{content_slug}"
        return self._make_request("GET", url)

    def get_playback_info(self, content_id):
        """
        Endpoint 6: Retrieves streaming URLs and playback information.
        Corresponds to: GET /api/internal/bff/v2/pages/666/spaces/334/widgets/244
        """
        print(f"Fetching playback info for content_id: {content_id}...")
        url = f"{self.BASE_URL}/api/internal/bff/v2/pages/666/spaces/334/widgets/244"
        
        # As per docs, these are the required capabilities parameters
        client_capabilities = {
            "ads": ["non_ssai"], "audio_channel": ["stereo"],
            "container": ["fmp4", "fmp4br", "ts"], "dvr": ["short"],
            "dynamic_range": ["sdr"], "encryption": ["plain"],
            "ladder": ["web", "tv", "phone"], "package": ["dash", "hls"],
            "resolution": ["sd", "hd", "fhd"], "video_codec": ["h264"],
            "video_codec_non_secure": ["h264"]
        }
        drm_parameters = {
            "hdcp_version": ["HDCP_V2_2"],
            "widevine_security_level": [],
            "playready_security_level": []
        }
        
        params = {
            "content_id": content_id,
            "client_capabilities": json.dumps(client_capabilities, separators=(',', ':')),
            "drm_parameters": json.dumps(drm_parameters, separators=(',', ':'))
        }
        
        return self._make_request("GET", url, params=params)

    def crawl(self, max_trays=3, max_items_per_tray=5):
        """
        Executes the content traversal strategy to crawl the site.
        """
        homepage_data = self.get_home_page()
        if not homepage_data:
            print("Failed to fetch homepage. Aborting crawl.")
            return

        all_content_data = []

        try:
            # Find the main content space in the homepage response
            content_wrappers = homepage_data['success']['page']['spaces']['content']['widget_wrappers']
            
            trays_processed = 0
            for wrapper in content_wrappers:
                if trays_processed >= max_trays:
                    break
                
                widget_data = wrapper.get('widget', {}).get('data', {})
                tray_title = widget_data.get('title', 'Untitled Tray')
                items = widget_data.get('items', [])
                
                if not items:
                    continue

                print(f"\n--- Processing Tray: {tray_title} ---")
                
                items_processed = 0
                for item in items:
                    if items_processed >= max_items_per_tray:
                        break
                        
                    # Extract the navigation link to the content detail page
                    content_link = item.get('actions', {}).get('on_click', [{}])[0].get('page_navigation', {}).get('page_url')
                    if not content_link:
                        continue
                    
                    # 5. Get Content Details
                    details = self.get_content_details(content_link)
                    if not details:
                        continue
                    
                    try:
                        hero_widget_data = details['success']['page']['spaces']['hero']['widget_wrappers'][0]['widget']['data']
                        content_id = hero_widget_data.get('content_id')
                        title = hero_widget_data.get('title')
                        description = hero_widget_data.get('description')
                        content_type = hero_widget_data.get('content_type')
                        
                        print(f"  > Found Content: '{title}' (ID: {content_id})")

                        # 6. Get Playback Info
                        playback_info = self.get_playback_info(content_id)
                        if playback_info:
                            media_asset = playback_info['success']['widget_wrapper']['widget']['data']['media_asset']
                            stream_url = media_asset.get('primary', {}).get('content_url')
                            
                            content_item = {
                                'title': title,
                                'description': description,
                                'content_id': content_id,
                                'content_type': content_type,
                                'stream_url': stream_url
                            }
                            all_content_data.append(content_item)
                            print(f"    - Stream URL found.")
                        
                        items_processed += 1

                    except (KeyError, IndexError) as e:
                        print(f"    - Could not parse content details: {e}")
                        continue
                        
                trays_processed += 1
                
        except (KeyError, TypeError) as e:
            print(f"Error parsing homepage structure: {e}")
            
        return all_content_data


if __name__ == '__main__':
    # IMPORTANT: You must provide your own valid authentication details.
    # These can often be found by inspecting the network requests in your
    # browser's developer tools when logged into Hotstar.
    USER_TOKEN = "YOUR_X-HS-USERTOKEN_HERE"  # e.g., "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9..."
    DEVICE_ID = "YOUR_X-HS-DEVICE-ID_HERE"   # e.g., "219a06-92f4d3-3cf707-a5941"

    if USER_TOKEN == "YOUR_X-HS-USERTOKEN_HERE" or DEVICE_ID == "YOUR_X-HS-DEVICE-ID_HERE":
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
        print("!!! PLEASE UPDATE THE USER_TOKEN AND DEVICE_ID VALUES !!!")
        print("!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!!")
    else:
        # Initialize and run the crawler
        crawler = HotstarCrawler(user_token=USER_TOKEN, device_id=DEVICE_ID)
        
        # Crawl the first 3 trays and the first 5 items in each tray
        crawled_data = crawler.crawl(max_trays=3, max_items_per_tray=5)

        # Print the final compiled data
        print("\n\n" + "="*50)
        print("CRAWLING COMPLETE. GATHERED DATA:")
        print("="*50)
        
        if crawled_data:
            print(json.dumps(crawled_data, indent=2))
        else:
            print("No data was crawled. Please check your credentials and the site's API status.")