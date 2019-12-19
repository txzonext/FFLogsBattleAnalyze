import os
import sys
import configparser
from urllib.parse import urlparse

import FFLogsBattleAnalyzer as analyzer

import asyncio
import discord

config = configparser.ConfigParser()
config.read(os.path.dirname(__file__) + os.sep + 'settings.ini', encoding='utf-8')

client = None

# 引数処理
# 引数指定なし: settings.ini内の DISCORD_CHANNEL_ID で指定したIDのDiscordのテキストチャンネルから
#               最新のFFLogs BotからのWebhook投稿URLを取得
if len(sys.argv) <= 1:
    class DiscordClient(discord.Client):
        '''
        コールバック関数を設定できる、discord.Clientを継承したクラス
        '''
        def __init__(self, callback=None, loop=None, **options):
            super(DiscordClient, self).__init__(loop=loop, **options)
            self.callback = callback

        # 接続完了時の処理
        async def on_ready(self):
            channel = self.get_channel(int(config.get('DEFAULT', 'DISCORD_CHANNEL_ID')))
            if channel is None:
                await self.close()
                self.callback(RuntimeError('Channel ID "{}" is not found.'.format(config.get('DEFAULT', 'DISCORD_CHANNEL_ID'))))
                return
            
            if channel.type != discord.ChannelType.text:
                await self.close()
                self.callback(RuntimeError('Channel ID "{}" is not Text Channel.'.format(config.get('DEFAULT', 'DISCORD_CHANNEL_ID'))))
                return

            completed_url = []
            for message in await channel.history().flatten():
                if len(message.embeds) <= 0:
                    continue

                url = urlparse(message.embeds[0].url)
                if url.scheme in ['http', 'https'] and 'fflogs.com' in url.netloc and url.path.startswith('/reports/'):
                    if message.author == client.user:
                        completed_url.append(url.path)
                        continue

                    if url.path in completed_url:
                        self.callback(RuntimeError('URL: {} has already analyzed.'.format(url.geturl())))
                        return

                    if self.callback is not None:
                        self.callback(url.path.split('/')[2])
                    break
            await self.close()

    # コールバック用データとコールバック関数
    callback_data = []
    def callback(data):
        callback_data.append(data)

    # Discordに接続
    client = DiscordClient(callback, loop=asyncio.new_event_loop())
    client.run(config.get('DEFAULT', 'DISCORD_TOKEN'))

    # コールバックが呼び出されていない場合はエラー
    if len(callback_data) == 0:
        raise RuntimeError('Failed to get report ID from Discord.')

    # コールバック用リストに例外が設定されている場合raise
    elif isinstance(callback_data[0], Exception):
        raise callback_data[0]

    # コールバック用リストからレポートIDを設定
    elif isinstance(callback_data[0], str):
        report_id = callback_data[0]
    else:
        raise RuntimeError('Failed to get report ID from Discord.')

# 引数指定あり: FFLogs URL指定の場合
elif (sys.argv[1].startswith('https://') or sys.argv[1].startswith('http://')) and 'fflogs.com/reports/' in sys.argv[1]:
    report_id = sys.argv[1].split('/')[4]
# 引数指定あり: その他 ⇒ レポートID直指定
else:
    report_id = sys.argv[1]

# 分析処理開始
print('###################################\n'
      ' Start analysis.\n'
      '    Target URL: ' + analyzer.FFLOGS_DPS_URL.format(report_id=report_id, boss_id=analyzer.FFLOGS_TARGET_BOSS_ID) + '\n'
      '###################################\n'
)

result_text = analyzer.get_analysys_result(config.get('DEFAULT', 'FFLOGS_API_KEY'), report_id)

# 分析結果出力
if client is None:
    print('###################################\n'
          ' Results\n' 
          '###################################\n'
    )
    print(result_text)

else:
    client = discord.Client(loop=asyncio.new_event_loop())
    
    @client.event
    async def on_ready():
        if not client.is_ready():
            return
        
        channel = client.get_channel(int(config.get('DEFAULT', 'DISCORD_CHANNEL_ID')))
        embed = discord.Embed(
                title='Analysis completed.',
                url=analyzer.FFLOGS_DPS_URL.format(report_id=report_id, boss_id=analyzer.FFLOGS_TARGET_BOSS_ID),
                color=0x7cfc00
            )
        embed.add_field(name='Result', value=result_text)

        if not client.is_ready():
            return

        await channel.send(embed=embed)
        await client.close()

    client.run(config.get('DEFAULT', 'DISCORD_TOKEN'))
