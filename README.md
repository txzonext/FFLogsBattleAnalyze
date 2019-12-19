# FFLogsBattleAnalyze

## Require
Install Google Chrome, Python and Libraries.  
[Google Chrome](https://www.google.com/intl/ja/chrome/)  
[Python 3.7 - Microsoft Store](https://www.microsoft.com/store/productId/9NJ46SX7X90P)  

`pip install chromedriver-binary==79.0.3945.36.0 requests bs4 selenium tqdm discord.py`  

## Setup
Set your FF Logs API key to the variable `FFLOGS_API_KEY` in `main.py`.  

If you want to get the report ID automatically from the Discord webhook,  
set the Discord Bot token to `DISCORD_TOKEN` and the channel ID to `DISCORD_CHANNEL_ID`.  

## Execute
If report URL is *https://www.fflogs.com/reports/abCDeFgHijkLmn/*  
`python main.py abCDeFgHijkLmn`  

OR

If you setuped Discord Token and Discord server settings,
just run `python main.py`.