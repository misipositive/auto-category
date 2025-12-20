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
current_category = "Just Chatting"
last_token_refresh = 0
TOKEN_REFRESH_INTERVAL = 3600  # Changed to 1 hour for better safety margin
discord_games_cache = {}
last_discord_fetch = 0
discord_games_persistent = {}  # Persistent storage that accumulates all games ever seen
failed_categories = set()  # Track categories that failed to match on Twitch

# Blacklist: Common engine/utility processes that run for multiple games
# These should never be used for category detection
process_blacklist = {
    "unitycrashhandler64.exe",
    "unitycrashhandler32.exe",
    "crashreporter.exe",
    "crashhandler.exe",
    "unrealcefsubprocess.exe",
    "cefprocess.exe",
    "steamservice.exe",
    "steam.exe",
    "epicgameslauncher.exe",
    "easyanticheat.exe",
    "battleye.exe",
}

# Manual overrides - highest priority (50-90)
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
    "Vscodium.exe": 50,
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
    "code.exe": "Software and Game Development",
    "cursor.exe": "Software and Game Development",
    "VsCode.exe": "Software and Game Development",
    "vscodium.exe": "Software and Game Development",
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

# Create lowercase lookups once at module level
process_priorities_lower = {k.lower(): v for k, v in process_priorities.items()}
process_categories_lower = {k.lower(): v for k, v in process_categories.items()}

def script_description():
    return "Automatically updates Twitch category based on running applications. Uses manual database + Discord detectable games as fallback. Discord database updates on each OBS startup."

def script_properties():
    props = obs.obs_properties_create()
    obs.obs_properties_add_button(props, "login_button", "Login with Twitch", login_button_clicked)
    obs.obs_properties_add_button(props, "refresh_token_button", "Refresh Token", refresh_token_button_clicked)
    obs.obs_properties_add_button(props, "refresh_discord_button", "Refresh Discord Database", refresh_discord_button_clicked)
    return props

def script_load(settings):
    global client_id, client_secret, access_token, refresh_token
    client_id, client_secret = load_config()
    load_access_tokens()
    load_persistent_discord_database()  # Load accumulated games from disk
    fetch_discord_games()  # Fetch latest from Discord and merge
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
        monitor_thread.join(timeout=2)
    
    if server_thread and server_thread.is_alive():
        server_thread.join(timeout=2)

def load_config():
    config_path = os.path.join(os.path.dirname(__file__), 'config.json')
    if os.path.exists(config_path):
        try:
            with open(config_path, 'r') as f:
                config = json.load(f)
                return config.get('client_id'), config.get('client_secret')
        except (json.JSONDecodeError, IOError) as e:
            script_log(f"Error reading config.json: {e}")
    else:
        script_log("Config file not found. Please create a config.json file with your client_id and client_secret.")
    return None, None

def script_log(message):
    obs.script_log(obs.LOG_INFO, f"[Twitch Category Updater] {message}")

def login_button_clicked(props, prop):
    global auth_initiated
    auth_initiated = False
    threading.Thread(target=start_oauth_flow, daemon=True).start()
    return True

def refresh_token_button_clicked(props, prop):
    if refresh_access_token():
        script_log("Token refreshed successfully!")
        if not monitor_thread or not monitor_thread.is_alive():
            start_process_monitor()
    else:
        script_log("Failed to refresh token. Please re-authenticate.")
    return True

def refresh_discord_button_clicked(props, prop):
    threading.Thread(target=fetch_discord_games, args=(True,), daemon=True).start()
    return True

def should_refresh_token():
    global last_token_refresh
    time_since_refresh = time.time() - last_token_refresh
    return time_since_refresh >= TOKEN_REFRESH_INTERVAL

def start_oauth_flow():
    global redirect_uri, server_thread
    
    try:
        port = 1111  # Fixed port for OAuth redirect URL
        
        # Check if port is available
        try:
            test_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            test_socket.bind(('localhost', port))
            test_socket.close()
        except OSError:
            script_log(f"ERROR: Port {port} is already in use. Please close the application using it or change the port in the script (line 202) and Twitch Developer Console.")
            return
        
        redirect_uri = f"http://localhost:{port}"
        
        class OAuthHandler(BaseHTTPRequestHandler):
            def log_message(self, format, *args):
                pass  # Suppress HTTP server logs
            
            def do_GET(self):
                if "code=" in self.path:
                    code = self.path.split("code=")[1].split("&")[0]
                    success = get_access_token(code)
                    self.send_response(200)
                    self.send_header('Content-type', 'text/html')
                    self.end_headers()
                    if success:
                        self.wfile.write(b"<h1>Authentication successful!</h1><p>You can close this window and return to OBS.</p>")
                        start_process_monitor()
                    else:
                        self.wfile.write(b"<h1>Authentication failed!</h1><p>Please check OBS logs and try again.</p>")
                    threading.Thread(target=lambda: time.sleep(2) or self.server.shutdown()).start()
                else:
                    self.send_response(400)
                    self.end_headers()
                    self.wfile.write(b"<h1>Invalid request</h1>")
        
        server = HTTPServer(('localhost', port), OAuthHandler)
        server_thread = threading.Thread(target=server.serve_forever, daemon=True)
        server_thread.start()
        
        auth_url = f"https://id.twitch.tv/oauth2/authorize?client_id={client_id}&redirect_uri={redirect_uri}&response_type=code&scope=channel:manage:broadcast"
        webbrowser.open(auth_url)
        script_log(f"OAuth server started on port {port}. Opening browser for authentication...")
        
    except Exception as e:
        script_log(f"Failed to start OAuth flow: {e}")

def get_access_token(code):
    global access_token, refresh_token, last_token_refresh
    token_url = "https://id.twitch.tv/oauth2/token"
    data = {
        "client_id": client_id,
        "client_secret": client_secret,
        "code": code,
        "grant_type": "authorization_code",
        "redirect_uri": redirect_uri
    }
    try:
        response = requests.post(token_url, data=data, timeout=30)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data["access_token"]
        refresh_token = token_data["refresh_token"]
        last_token_refresh = time.time()
        save_access_tokens(access_token, refresh_token)
        script_log("Successfully logged in!")
        return True
    except requests.exceptions.RequestException as e:
        script_log(f"Failed to obtain access token: {e}")
        return False

def save_access_tokens(access_token, refresh_token):
    token_path = os.path.join(os.path.dirname(__file__), 'tokens.json')
    try:
        with open(token_path, 'w') as f:
            json.dump({
                "access_token": access_token, 
                "refresh_token": refresh_token,
                "timestamp": time.time()
            }, f)
    except IOError as e:
        script_log(f"Failed to save tokens: {e}")
        
def refresh_access_token():
    global access_token, refresh_token, last_token_refresh
    
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
        response = requests.post(token_url, data=data, timeout=30)
        response.raise_for_status()
        token_data = response.json()
        access_token = token_data["access_token"]
        if "refresh_token" in token_data:
            refresh_token = token_data["refresh_token"]
        last_token_refresh = time.time()
        save_access_tokens(access_token, refresh_token)
        script_log("Successfully refreshed access token!")
        return True
    except requests.exceptions.RequestException as e:
        script_log(f"Failed to refresh access token: {e}")
        access_token = None
        refresh_token = None
        return False

def load_access_tokens():    
    global access_token, refresh_token, last_token_refresh
    token_path = os.path.join(os.path.dirname(__file__), 'tokens.json')
    if os.path.exists(token_path):
        try:
            with open(token_path, 'r') as f:
                data = json.load(f)
                access_token = data.get("access_token")
                refresh_token = data.get("refresh_token")
                last_token_refresh = data.get("timestamp", 0)
        except (json.JSONDecodeError, IOError) as e:
            script_log(f"Error loading tokens: {e}")

def fetch_discord_games(force_refresh=False):
    global discord_games_cache, discord_games_persistent, last_discord_fetch
    
    # Only skip if we already fetched during this session (unless forced)
    if not force_refresh and last_discord_fetch > 0:
        return
    
    try:
        script_log("Fetching Discord detectable games database...")
        response = requests.get(
            "https://discord.com/api/v9/applications/detectable",
            timeout=15
        )
        response.raise_for_status()
        games_data = response.json()
        
        # Build current cache: executable -> game name
        new_cache = {}
        new_games_count = 0
        
        for game in games_data:
            if 'executables' in game and 'name' in game:
                for exe in game['executables']:
                    if 'name' in exe:
                        # Extract just the filename, not the path
                        exe_full = exe['name'].lower()
                        # Handle both "game.exe" and "folder/game.exe" formats
                        exe_name = exe_full.split('/')[-1] if '/' in exe_full else exe_full
                        
                        # Skip blacklisted utility processes
                        if exe_name in process_blacklist:
                            continue
                        
                        game_name = game['name']
                        new_cache[exe_name] = game_name
                        
                        # Add to persistent database if not already there
                        if exe_name not in discord_games_persistent:
                            discord_games_persistent[exe_name] = game_name
                            new_games_count += 1
        
        discord_games_cache = new_cache
        last_discord_fetch = time.time()
        
        if new_games_count > 0:
            script_log(f"Discord database updated: {len(discord_games_cache)} current games, {new_games_count} new games added to persistent database")
            save_persistent_discord_database()
        else:
            script_log(f"Discord database refreshed: {len(discord_games_cache)} current games, {len(discord_games_persistent)} total accumulated")
        
    except requests.exceptions.RequestException as e:
        script_log(f"Failed to fetch Discord games: {e}")
        # Use persistent database as fallback
        if discord_games_persistent:
            discord_games_cache = discord_games_persistent.copy()
            script_log(f"Using persistent database: {len(discord_games_cache)} games")

def load_persistent_discord_database():
    """Load the accumulated Discord games database from disk"""
    global discord_games_persistent
    db_path = os.path.join(os.path.dirname(__file__), 'discord_games_persistent.json')
    if os.path.exists(db_path):
        try:
            with open(db_path, 'r') as f:
                data = json.load(f)
                discord_games_persistent = data.get('games', {})
                timestamp = data.get('timestamp', 0)
                script_log(f"Loaded persistent Discord database: {len(discord_games_persistent)} games (last updated: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(timestamp))})")
        except (json.JSONDecodeError, IOError) as e:
            script_log(f"Error loading persistent Discord database: {e}")
            discord_games_persistent = {}
    else:
        script_log("No persistent Discord database found, will create new one")
        discord_games_persistent = {}

def save_persistent_discord_database():
    """Save the accumulated Discord games database to disk"""
    db_path = os.path.join(os.path.dirname(__file__), 'discord_games_persistent.json')
    try:
        with open(db_path, 'w') as f:
            json.dump({
                'games': discord_games_persistent,
                'timestamp': time.time(),
                'total_games': len(discord_games_persistent)
            }, f, indent=2)
        script_log(f"Saved persistent Discord database: {len(discord_games_persistent)} total games")
    except IOError as e:
        script_log(f"Failed to save persistent Discord database: {e}")

def update_twitch_category(category):
    global current_category, failed_categories
    
    if category == current_category:
        return True
    
    # Skip categories we know don't have exact matches on Twitch
    if category in failed_categories:
        return False
        
    if not access_token:
        script_log("Not authenticated with Twitch")
        return False
    
    headers = {
        'Client-ID': client_id,
        'Authorization': f'Bearer {access_token}',
        'Content-Type': 'application/json'
    }
    
    try:
        config_path = os.path.join(os.path.dirname(__file__), 'config.json')
        with open(config_path, 'r') as f:
            config = json.load(f)
            broadcaster_name = config.get('broadcaster_name')
        
        if not broadcaster_name:
            script_log("broadcaster_name not found in config.json")
            return False
    except (IOError, json.JSONDecodeError) as e:
        script_log(f"Error reading broadcaster name from config: {e}")
        return False
    
    try:
        max_retries = 3
        retry_delay = 2
        
        for attempt in range(max_retries):
            try:
                user_response = requests.get(
                    f'https://api.twitch.tv/helix/users?login={broadcaster_name}',
                    headers=headers,
                    timeout=15
                )
                if user_response.status_code == 401:
                    script_log("Token invalid during user lookup, attempting refresh...")
                    if not refresh_access_token():
                        return False
                    headers['Authorization'] = f'Bearer {access_token}'
                    continue
                user_response.raise_for_status()
                break
            except requests.exceptions.RequestException as e:
                if attempt == max_retries - 1:
                    script_log(f"Failed to get user ID after {max_retries} attempts: {e}")
                    return False
                time.sleep(retry_delay)
        
        user_data = user_response.json().get('data', [])
        if not user_data:
            script_log(f"User not found: {broadcaster_name}")
            return False
            
        broadcaster_id = user_data[0]['id']
        
        category_response = requests.get(
            f'https://api.twitch.tv/helix/search/categories?query={requests.utils.quote(category)}',
            headers=headers,
            timeout=15
        )
        category_response.raise_for_status()
        categories = category_response.json().get('data', [])
        
        if not categories:
            script_log(f"Category not found on Twitch: {category}")
            return False
            
        # Only accept exact matches (case-insensitive)
        exact_match = next((cat for cat in categories if cat['name'].lower() == category.lower()), None)
        if not exact_match:
            script_log(f"No exact match for '{category}' on Twitch. Skipping update to avoid wrong category.")
            failed_categories.add(category)  # Remember this failed
            return False
            
        game_id = exact_match['id']
        actual_category = exact_match['name']
        
        update_response = requests.patch(
            f'https://api.twitch.tv/helix/channels?broadcaster_id={broadcaster_id}',
            headers=headers,
            json={'game_id': game_id},
            timeout=15
        )
        
        if update_response.status_code == 401:
            script_log("Token invalid during channel update, attempting refresh...")
            if refresh_access_token():
                headers['Authorization'] = f'Bearer {access_token}'
                update_response = requests.patch(
                    f'https://api.twitch.tv/helix/channels?broadcaster_id={broadcaster_id}',
                    headers=headers,
                    json={'game_id': game_id},
                    timeout=15
                )
        
        update_response.raise_for_status()
        current_category = category
        script_log(f"Successfully updated category to: {actual_category}")
        return True
        
    except requests.exceptions.RequestException as e:
        script_log(f"Failed to update category: {str(e)}")
        return False

def check_processes():
    try:
        highest_priority = -1
        selected_category = None
        
        for proc in psutil.process_iter(['name']):
            try:
                process_name = proc.info['name'].lower()
                
                # Skip blacklisted utility/engine processes
                if process_name in process_blacklist:
                    continue
                
                # Check manual database first (priority 50-90)
                if process_name in process_categories_lower:
                    priority = process_priorities_lower.get(process_name, 50)
                    if priority > highest_priority:
                        highest_priority = priority
                        selected_category = process_categories_lower[process_name]
                
                # Check persistent Discord database as fallback (priority 30)
                # This database continuously grows and never loses games
                elif process_name in discord_games_persistent:
                    priority = 30  # Lower than all manual entries
                    if priority > highest_priority:
                        highest_priority = priority
                        selected_category = discord_games_persistent[process_name]
                        
            except (psutil.NoSuchProcess, psutil.AccessDenied):
                continue
        
        return selected_category if selected_category is not None else "Just Chatting"
        
    except Exception as e:
        script_log(f"Error checking processes: {str(e)}")
        return "Just Chatting"

def validate_token():
    if not access_token:
        return False
    headers = {
        'Authorization': f'OAuth {access_token}'
    }
    try:
        response = requests.get('https://id.twitch.tv/oauth2/validate', headers=headers, timeout=10)
        if response.status_code == 200:
            return True
        elif response.status_code == 401:
            return False
        else:
            script_log(f"Unexpected status code during token validation: {response.status_code}")
            return False
    except requests.exceptions.RequestException as e:
        script_log(f"Error during token validation: {str(e)}")
        return False
    
def start_process_monitor():
    global monitor_thread, stop_monitoring
    stop_monitoring = False
    
    def monitor():
        consecutive_failures = 0
        max_consecutive_failures = 5
        
        while not stop_monitoring:
            try:
                if not client_id or not client_secret:
                    script_log("Missing client credentials. Please check config.json")
                    time.sleep(300)
                    continue
                
                if should_refresh_token():
                    script_log("1 hour elapsed, refreshing token automatically...")
                    if not refresh_access_token():
                        script_log("Automatic token refresh failed")
                        consecutive_failures += 1
                    else:
                        consecutive_failures = 0
                
                if consecutive_failures < max_consecutive_failures:
                    if not validate_token():
                        script_log("Token validation failed, attempting refresh...")
                        if not refresh_access_token():
                            consecutive_failures += 1
                            script_log(f"Token refresh failed. Consecutive failures: {consecutive_failures}")
                            time.sleep(min(60 * (2 ** consecutive_failures), 3600))
                            continue
                        else:
                            consecutive_failures = 0
                else:
                    script_log("Too many consecutive failures. Waiting 1 hour before retry...")
                    time.sleep(3600)
                    consecutive_failures = 0
                    continue
                    
                category = check_processes()
                if update_twitch_category(category):
                    consecutive_failures = 0
                else:
                    consecutive_failures += 1
                    
                time.sleep(60)
                
            except Exception as e:
                script_log(f"Error in monitor thread: {str(e)}")
                consecutive_failures += 1
                time.sleep(60)
    
    if monitor_thread and monitor_thread.is_alive():
        stop_monitoring = True
        monitor_thread.join(timeout=2)
    
    monitor_thread = threading.Thread(target=monitor, daemon=True)
    monitor_thread.start()
    script_log("Process monitor started")
