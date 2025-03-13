#### Installation 
1. Python version 3.9 or later, configured/loaded with OBS
2. required python libraries: requests, psutil
  `pip install requests psutil`
3. Place auto-category4.py in obs directory:
  `C:\Program Files\obs-studio\data\obs-plugins\frontend-tools\scripts`
4. Create `config.json` file in the same folder with your Twitch API credentials:
   `{"client_id": "YOUR_CLIENT_ID","client_secret": "YOUR_CLIENT_SECRET","broadcaster_name": "YOUR_TWITCH_USERNAME"}`
   
#### Obtaning Twitch API credentials (clientid,clientsecret):
- Go to the [Twitch Developer Console](https://dev.twitch.tv/)
- Login
- Register a new application
- Set a Name, Set OAuth Redirect URL to: http://localhost
- Client type: Confidential
- Category: Application Integration
- Copy Client ID, Client Secret: Paste in config.json

#### Using
- Launch OBS
- Tools -> Scripts > + Button > select auto-category4.py > Login With Twitch
- Login when prompted (required once per OBS session)

#### To add more games
- Edit these 2 lines in -> auto_category4.py
- `process_categories = {"minecraft.exe": "Minecraft",}`
- `process_priorities = {"minecraft.exe": 90,}`

#### Notes
login is only needed once per OBS session
