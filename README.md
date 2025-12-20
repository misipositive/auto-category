# update your dev.twitch app too `http://localhost:1111` if you're gonna use this version

#### Updates Tried to add: **Auto refresh**, **bigger games database**
- Auto refresh updates the twitch api token when it gets too old.
- Bigger games database: Thanks to ***@mee*** from Obs-Forums

#### Installation
1. Python version 3.9 or later, configured/loaded with OBS
2. required python libraries: requests, psutil
  `pip install requests psutil`
3. Place auto-category4.py in obs directory:
  `C:\Program Files\obs-studio\data\obs-plugins\frontend-tools\scripts`
4. Create `config.json` file in the same folder with your Twitch API credentials:
   `{"client_id": "YOUR_CLIENT_ID","client_secret": "YOUR_CLIENT_SECRET","broadcaster_name": "YOUR_TWITCH_USERNAME"}`
   
#### Obtaning Twitch API credentials (clientid,clientsecret):
- Go to the [Twitch Developer Console](https://dev.twitch.tv/): **Login**
- Create a Twitch application:
- **Name**: `OBS Category Updater` (or any name you prefer)
- **OAuth Redirect URLs**: `http://localhost:1111`
- **Category**: Application Integration
- Copy Client ID & new Client Secret: Paste in `config.json` we created on step 4.

**note**: the port `1111` must match in both Twitch App and the script (line 194). If changing it: Use a port number above 1024

#### Using
- Launch OBS
- Tools -> Scripts > + Button > select auto-category4.py > Login With Twitch
- **Login** required once per OBS Session 

#### To add more games
- Edit these 2 lines in -> auto_category4.py
- `process_categories = {"minecraft.exe": "Minecraft",}`
- `process_priorities = {"minecraft.exe": 90,}`

#### Notes
login is only needed once per OBS session
