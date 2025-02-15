## Instructions
- [Login] To get your Twitch API credentials from [Twitch Developer Console](https://dev.twitch.tv/console)
- [Register your application](https://dev.twitch.tv/console/apps)
- Top right Register application
- OAuth Redirect URLs: http://localhost 
- client id and secret id at bottom


- config.json & auto-category3.py should be in the same folder under `C:\Program Files\obs-studio\data\obs-plugins\frontend-tools\scripts`
- Create a `config.json` file with your credentials:
- (`config.json`)This how it should look
`{
    "client_id": "",
    "client_secret": "",
    "broadcaster_name": ""
}`

- Python 3.6+ (installed and configured with OBS)
- Python libraries: obspython, requests, psutil

## Note
- the script oauth needs to be refreshed every 4 hours
- meaning, click the refresh script, Login Button again, authenticate. 
now you have 4 more hours of automatic twitch categories
