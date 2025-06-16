import requests
import json
from datetime import date, timedelta

# Common headers and cookies from the documentation
COMMON_HEADERS = {
    'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/136.0.0.0 Safari/537.36',
    'Referer': 'https://areena.yle.fi/'
}

COMMON_COOKIES = {
    'yle_selva': '1749181611342597482'
}

def get_user_location():
    """
    Calls the User Location API to get the user's geographic information.
    """
    print("--- Calling User Location API ---")
    url = "https://locations.api.yle.fi/v4/address/current"
    params = {
        'app_id': 'analytics-sdk',
        'app_key': 'RVaxtSmiGRRUDos7uAmOCh6fReH9SEyg'
    }
    try:
        response = requests.get(url, params=params, headers=COMMON_HEADERS, cookies=COMMON_COOKIES)
        response.raise_for_status()  # Raise an exception for bad status codes
        print("Successfully retrieved user location.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling User Location API: {e}")
        return None

def get_tv_guide_navigation(build_id, target_date=None):
    """
    Calls the TV Guide Date Navigation API.
    """
    print(f"\n--- Calling TV Guide Navigation API for date: {target_date or 'today'} ---")
    url = f"https://areena.yle.fi/_next/data/{build_id}/fi/tv/opas.json"
    
    params = {}
    if target_date:
        params['t'] = target_date

    try:
        response = requests.get(url, params=params, headers=COMMON_HEADERS, cookies=COMMON_COOKIES)
        response.raise_for_status()
        print("Successfully retrieved TV guide navigation.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling TV Guide Navigation API: {e}")
        return None

def get_channel_schedule(channel_id, schedule_date):
    """
    Calls the Channel Schedule API for a specific channel and date.
    """
    print(f"\n--- Calling Channel Schedule API for channel: {channel_id} on date: {schedule_date} ---")
    url = f"https://areena.api.yle.fi/v1/ui/schedules/{channel_id}/{schedule_date}.json"
    
    params = {
        'yleReferer': f'tv.guide.{schedule_date}.tv_opas.{channel_id}.untitled_list',
        'language': 'fi',
        'v': '10',
        'client': 'yle-areena-web',
        'offset': '0',
        'limit': '100',
        'country': 'IN',
        'app_id': 'areena-web-items',
        'app_key': 'wlTs5D9OjIdeS9krPzRQR4I1PYVzoazN'
    }

    try:
        response = requests.get(url, params=params, headers=COMMON_HEADERS, cookies=COMMON_COOKIES)
        response.raise_for_status()
        print(f"Successfully retrieved schedule for {channel_id} on {schedule_date}.")
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Error calling Channel Schedule API for {channel_id} on {schedule_date}: {e}")
        return None

if __name__ == '__main__':
    # 1. Get User Location
    user_location_json = get_user_location()
    if user_location_json:
        print("User Location JSON:")
        print(json.dumps(user_location_json, indent=2))

    # 2. Get TV Guide Navigation
    # NOTE: The build_id changes over time. You may need to inspect network traffic
    # on areena.yle.fi to get a current one.
    current_build_id = "Q_35nL8jUwGOhxPC9wVX5" 
    today = date.today().strftime("%Y-%m-%d")
    
    tv_guide_nav_json = get_tv_guide_navigation(current_build_id, target_date=today)
    if tv_guide_nav_json:
        print("\nTV Guide Navigation JSON:")
        print(json.dumps(tv_guide_nav_json, indent=2))

    # 3. Get Channel Schedules for today for all specified channels
    channel_ids = [
        "yle-tv1",
        "yle-tv2",
        "yle-teema-fem",
        "tv-finland",
        "yle-areena"
    ]

    all_channel_schedules = {}
    for channel in channel_ids:
        schedule_json = get_channel_schedule(channel, today)
        if schedule_json:
            all_channel_schedules[channel] = schedule_json
    
    if all_channel_schedules:
        print("\n--- All Channel Schedules JSON ---")
        res = json.dumps(all_channel_schedules, indent=2)
        with open("yle-raw-data.json", "w") as f:
            f.write(res)