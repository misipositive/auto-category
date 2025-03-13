import obspython as obs # type: ignore
import json
import os
import requests
import webbrowser
import threading
from http.server import HTTPServer, BaseHTTPRequestHandler
import socket
import time
import psutil # type: ignore

client_id = None
client_secret = None
access_token = None
refresh_token = None
redirect_uri = None
auth_initiated = False
monitor_thread = None
server_thread = None
stop_monitoring = False
current_category = "Just Chatting"  # Initialize with default category

process_priorities = {
    "cs2.exe": 90,
    "leagueclient.exe": 90,
    "league of legends.exe": 90,
    "cursor.exe": 50,
    "code.exe": 50,
    "vscode.exe": 50,
    "pubg.exe": 90,
    "rocketleague.exe": 90,
    "amongus.exe": 90,
    "rainbow6.exe": 90,
    "r5apex.exe": 90,
    "r5apex_dx12.exe": 90,
    "cities.exe": 90,
    "cities2.exe": 90,
    "fortniteclient-win64-shipping.exe": 90,
    "gtav.exe": 90,
    "gta5.exe": 90,
    "rdr2.exe": 90,
    "valorant.exe": 90,
    "overwatch.exe": 90,
    "dota2.exe": 90,
    "minecraft.exe": 90,
    "cyberpunk2077.exe": 90,
    "shotcut.exe": 60,
    "jigsaw.exe": 90,
    "huntgame.exe": 90,
    "paladins.exe": 90,
    "BloonsTD6.exe": 90,
    "raft.exe": 90,
}

process_categories = {
    "bloonstd6.exe": "Bloons TD 6",
    "paladins.exe": "Paladins",
    "huntgame.exe": "Hunt: Showdown 1896",
    "cs2.exe": "Counter-Strike",
    "leagueclient.exe": "League of Legends",
    "league of legends.exe": "League of Legends",
    "cursor.exe": "Software and Game Development",
    "VsCode.exe": "Software and Game Development",
    "code.exe": "Software and Game Development",
    "pubg.exe": "PLAYERUNKNOWN'S BATTLEGROUNDS",
    "rocketleague.exe": "Rocket League",
    "amongus.exe": "Among Us",
    "rainbow6.exe": "Tom Clancy's Rainbow Six Siege",
    "r5apex.exe": "Apex Legends",
    "r5apex_dx12.exe": "Apex Legends",
    "cities.exe": "Cities: Skylines",
    "cities2.exe": "Cities: Skylines II",
    "fortniteclient-win64-shipping.exe": "Fortnite",
    "gtav.exe": "Grand Theft Auto V",
    "gta5.exe": "Grand Theft Auto V",
    "rdr2.exe": "Red Dead Redemption 2",
    "valorant.exe": "VALORANT",
    "overwatch.exe": "Overwatch 2",
    "dota2.exe": "Dota 2",
    "minecraft.exe": "Minecraft",
    "cyberpunk2077.exe": "Cyberpunk 2077",
    "shotcut.exe": "Editor's Hell",
    "jigsaw.exe": "Jigsaw Puzzle Dreams",
    "raft.exe": "Raft"
}

def script_description():
    return "Automatically updates Twitch category based on running applications."

def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_button(props, "login_button", "Login with Twitch", login_button_clicked)
    return props

def script_load(settings):
    global client_id, client_secret, access_token, refresh_token
    client_id, client_secret = load_config()
    load_access_tokens()
    if access_token and refresh_token:
        if validate_token() or refresh_access_token():
            start_process_monitor()
        else:
            script_log("Failed to validate or refresh tokens. Please re-authenticate using the 'Login with Twitch' button.")
    else:
        script_log("No valid tokens found. Please authenticate using the 'Login with Twitch' button.")


def script_unload():
    global stop_monitoring, monitor_thread, server_thread
    stop_monitoring = True
    
    if monitor_thread and monitor_thread.is_alive():
        monitor_thread.join(timeout=1)
    
    if server_thread and server_thread.is_alive():
        server_thread.join(timeout=1)

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get('client_id'), config.get('client_secret')
        except json.JSONDecodeError:
            script_log("Error: config.json is not a valid JSON file.")
        except IOError:
            script_log("Error: Unable to read config.json file.")
    else:
        script_log("Config file not found. Please create a config.json file with your client_id and client_secret.")
    return None, None

def script_log(message):
    obs.script_log(obs.LOG_INFO, message)

def login_button_clicked(props, prop):
    global auth_initiated
    auth_initiated = False
    threading.Thread(target=start_oauth_server, daemon=True).start()
    start_auth()
    return True

def start_auth():
    auth_url = f"https://id.twitch.tv/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=channel:manage:broadcast"
    webbrowser.open(auth_url)

def find_free_port():
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as s:
        s.bind(('', 0))
        return s.getsockname()[1]

def start_oauth_server():
    global redirect_uri
    port = 80
    redirect_uri = "http://localhost"

    class OAuthHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            if "code=" in self.path:
                code = self.path.split("code=")[1].split("&")[0]
                get_access_token(code)
                self.send_response(200)
                self.end_headers()
                self.wfile.write(b"Authentication successful! You can close this window.")
                threading.Thread(target=self.server.shutdown).start()

    server = HTTPServer(('localhost', port), OAuthHandler)
    threading.Thread(target=server.serve_forever, daemon=True).start()
    script_log(f"OAuth server started on port {port}")

def start_auth():
    start_oauth_server()
    auth_url = f"https://id.twitch.tv/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=channel:manage:broadcast"
    webbrowser.open(auth_url)

def get_access_token(code):
    global access_token, refresh_token
    token_url = "https://id.twitch.tv/oauth2/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]
        save_access_tokens(access_token, refresh_token)
        script_log("Successfully logged in!")
    except requests.exceptions.RequestException as e:
        script_log(f"Failed to obtain access token: {e}")

def save_access_tokens(access_token, refresh_token):
    token_path = os.path.join(os.path.dirname(__file__), 'tokens.json')
    with open(token_path, 'w') as f:
        json.dump({"access_token": access_token, "refresh_token": refresh_token}, f)
        
def refresh_access_token():
    global access_token, refresh_token
    if not refresh_token:
        script_log("No refresh token available. Please re-authenticate.")
        return False

    token_url = "https://id.twitch.tv/oauth2/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "grant_type": "refresh_token",
        "refresh_token": refresh_token
    }
    try:
        response = requests.post(token_url, data=data)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data["access_token"]
        if "refresh_token" in token_data:
            refresh_token = token_data["refresh_token"]
        save_access_tokens(access_token, refresh_token)
        script_log("Successfully refreshed access token!")
        return True
    except requests.exceptions.RequestException as e:
        script_log(f"Failed to refresh access token: {e}")
        return False

def load_access_tokens():    
    global access_token, refresh_token
    token_path = os.path.join(os.path.dirname(__file__), 'tokens.json')
    if os.path.exists(token_path):
        with open(token_path, 'r') as f:
            data = json.load(f)
            access_token = data.get("access_token")
            refresh_token = data.get("refresh_token")

def update_twitch_category(category):
    global current_category
    
    if category == current_category:
        return
        
    if not access_token:
        script_log("Not authenticated with Twitch")
        return
    
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {access_token}'
    }
    
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    with open(config_path, 'r') as f:
        config = json.load(f)
        broadcaster_name = config.get('broadcaster_name')
    
    try:
        # Get user ID
        max_retries = 3
        retry_delay = 5  # seconds
        
        for attempt in range(max_retries):
            try:
                user_response = requests.get(
                    f'https://api.twitch.tv/helix/users?login={broadcaster_name}',
                    headers=headers,
                    timeout=10
                )
                user_response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    raise
                time.sleep(retry_delay)
        broadcaster_id = user_response.json()['data'][0]['id']
        
        # Search for category
        category_response = requests.get(
            f'https://api.twitch.tv/helix/search/categories?query={category}',
            headers=headers
        )
        category_response.raise_for_status()
        categories = category_response.json()['data']
        
        if not categories:
            script_log(f"Category not found: {category}")
            return
            
        # Find the exact match or closest match
        exact_match = next((cat for cat in categories if cat['name'].casefold() == category.casefold()), None)
        if exact_match:
            game_id = exact_match['id']
        else:
            # If no exact match, use the first result
            game_id = categories[0]['id']
            script_log(f"Exact category not found. Using closest match: {categories[0]['name']}")
        
        # Update channel
        update_response = requests.patch(
            f'https://api.twitch.tv/helix/channels?broadcaster_id={broadcaster_id}',
            headers=headers,
            json={'game_id': game_id}
        )
        update_response.raise_for_status()
        current_category = category  # Update our tracking variable
        script_log(f"Successfully updated category to: {category}")
        
    except requests.exceptions.RequestException as e:
        script_log(f"Failed to update category: {str(e)}")


def check_processes():
    try:
        highest_priority = -1
        selected_category = None
        
        process_priorities_fold = {k.casefold(): v for k, v in process_priorities.items()}
        process_categories_fold = {k.casefold(): v for k, v in process_categories.items()}
        
        for proc in psutil.process_iter(['name']):
            process_name = proc.info['name'].casefold()
            if process_name in process_categories_fold:
                priority = process_priorities_fold.get(process_name, 0)
                if priority > highest_priority:
                    highest_priority = priority
                    selected_category = process_categories_fold[process_name]
        
        if selected_category is None:
            return "Just Chatting"  # Explicitly return "Just Chatting" if no match found
        else:
            return selected_category
    except Exception as e:
        script_log(f"Error checking processes: {str(e)}")
        return "Just Chatting"  # Default to "Just Chatting" in case of error

def validate_token():
    if not access_token:
        return False
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {access_token}'
    }
    try:
        response = requests.get('https://id.twitch.tv/oauth2/validate', headers=headers)
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            return False  # Token is invalid, but might be refreshable
        else:
            script_log(f"Unexpected status code during token validation: {response.status_code}")
            return False
    except Exception as e:
        script_log(f"Error during token validation: {str(e)}")
        return False
    
def start_process_monitor():
    global monitor_thread, stop_monitoring
    stop_monitoring = False
    
    def monitor():
        while not stop_monitoring:
            try:
                if not validate_token():
                    script_log("Token expired or invalid. Please re-authenticate.")
                    time.sleep(60)
                    continue
                    
                category = check_processes()
                update_twitch_category(category)
                time.sleep(60)
            except Exception as e:
                script_log(f"Error in monitor thread: {str(e)}")
                time.sleep(60)
    
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()