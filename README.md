# Auto-Category
Updates Twitch.tv category based on running program.
if minecraft.exe running -> update twitch category to "Minecraft"
## Installation & Requirments 
1. Python version 3.9 or later, configured/loaded with OBS
2. Python libraries: requests, psutil
  `pip install requests psutil`
3. Place `auto-category4.py` in:
  `C:\Program Files\obs-studio\data\obs-plugins\frontend-tools\scripts`
4. Create a `config.json` file in the same folder with your Twitch API credentials:
  `{"client_id": "YOUR_CLIENT_ID","client_secret": "YOUR_CLIENT_SECRET","broadcaster_name": "YOUR_TWITCH_USERNAME"}`

5. To obtain Twitch API credentials:
Go to the Twitch Developer Console
Register a new application
Set OAuth Redirect URL to: http://localhost
Copy the Client ID and Client Secret

## Usage
Launch OBS
Tools -> Scripts > + Button > select auto-category4.py > Login With Twitch
Login when prompted (required once per OBS session)

## Add more games
Edit these 2 lines in -> auto_category4.py
`process_categories = {"minecraft.exe": "Minecraft",}`
`process_priorities = {"minecraft.exe": 90,}`

Example: 
- `"game or app in lowercase.exe" : "Category like it is from twitch categories"`
- `"vscode.exe" : "Software and Game Development"`

## Notes
Login is only needed once per OBS session
