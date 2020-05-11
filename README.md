# FFLogsBattleAnalyze

## Require
Install Google Chrome, Python and Libraries.  
[Firefox](https://www.mozilla.org/ja/firefox/new/)  
[Python 3.8 - Microsoft Store](https://www.microsoft.com/store/productId/9MSSZTT1N39L)  

`pip install -r requirements.txt`  

## Setup
Set your FF Logs API key to the variable `FFLOGS_API_KEY` in `settings.ini`.  

If you want to get the report ID automatically from the Discord webhook,  
set the Discord Bot token to `DISCORD_TOKEN` and the channel ID to `DISCORD_CHANNEL_ID`.  

## Execute
If report URL is *https://www.fflogs.com/reports/abCDeFgHijkLmn/*  
`python ./main.py abCDeFgHijkLmn`  

OR

If you setuped Discord Token and Discord server settings,
just run `python main.py`.
