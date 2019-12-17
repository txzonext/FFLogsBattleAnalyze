import sys
import time
import requests
import tqdm

from statistics import mean
from selenium import webdriver
import chromedriver_binary
from bs4 import BeautifulSoup

import asyncio
import discord
import traceback

# FFLogs APIキー
FFLOGS_API_KEY = ''

# Discord Bot アクセストークン
DISCORD_TOKEN = ''

# Discord テキストチャンネルID
DISCORD_CHANNEL_ID = 000000000000000000

# ソート用ジョブ名配列
JOB_SORT_RANK = ['DarkKnight', 'Warrior', 'Gunbreaker', 'Paladin', 'WhiteMage', 'Astrologian', 'Scholar', 'Samurai', 'Monk', 'Dragoon', 'Ninja', 'Bard', 'Machinist', 'Dancer', 'BlackMage', 'Summoner', 'RedMage', 'Total']

FFLOGS_TARGET_ZONE_ID = 887  # The Epic of Alexander
FFLOGS_TARGET_BOSS_ID = 1050 # The Epic of Alexander
FFLOGS_API_FIGHT_URL = 'https://www.fflogs.com/v1/report/fights/{report_id}?api_key={api_key}'
FFLOGS_DPS_URL = 'https://www.fflogs.com/reports/{report_id}#boss={boss_id}&difficulty=100&type=damage-done&phase={phase_num}'
FFLOGS_URL_FIGHT_QUERY = '&fight={fight_id}'

# 引数処理
# 引数指定なし: 「DISCORD_CHANNEL_ID」で指定したDiscordのテキストチャンネルから
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
            channel = self.get_channel(DISCORD_CHANNEL_ID)
            if channel is None:
                await self.close()
                raise RuntimeError('Channel ID "{}" is not found.'.format(DISCORD_CHANNEL_ID))
            
            if channel.type != discord.ChannelType.text:
                await self.close()
                raise RuntimeError('Channel ID "{}" is not Text Channel.'.format(DISCORD_CHANNEL_ID))

            for message in await channel.history().flatten():
                if len(message.embeds) <= 0:
                    continue

                if message.embeds[0].url.startswith('https://') and 'fflogs.com/reports/' in message.embeds[0].url:
                    if self.callback is not None:
                        self.callback(message.embeds[0].url.split('/')[4])
                    break
            await self.close()

    # コールバック用データとコールバック関数
    callback_data = []
    def callback(data):
        callback_data.append(data)

    # Discordに接続
    client = DiscordClient(callback)
    client.run(DISCORD_TOKEN)

    # コールバックが呼び出されていない場合はエラー
    if len(callback_data) == 0:
        raise RuntimeError('Failed to get report ID from Discord.')

    # コールバック用リストからレポートIDを設定
    report_id = callback_data[0]

# 引数指定あり: FFLogs URL指定の場合
elif (sys.argv[1].startswith('https://') or sys.argv[1].startswith('http://')) and 'fflogs.com/reports/' in sys.argv[1]:
    report_id = sys.argv[1].split('/')[4]
# 引数指定あり: その他 ⇒ レポートID直指定
else:
    report_id = sys.argv[1]

class Actor:
    '''
    Actor: プレイヤーなどのキャラクターを表すクラス
    '''
    def __init__(self, name, job, phase_count):
        self.name = name
        self.job = job
        self.dps = [0] * phase_count

    def __lt__(self, other):
        # self < other
        return JOB_SORT_RANK.index(self.job) < JOB_SORT_RANK.index(other.job)

    def __repr__(self):
        return self.name + ': ' + str(self.dps)

# FFLogs APIから戦闘情報を取得
res = requests.get(FFLOGS_API_FIGHT_URL.format(report_id=report_id, api_key=FFLOGS_API_KEY))
res.raise_for_status()

# フェーズ/インターミッション情報を戦闘情報から取得
fights_data = res.json()
for phase in fights_data['phases']:
    if phase['boss'] == FFLOGS_TARGET_BOSS_ID:
        phases = phase['phases']
        intermissions = phase['intermissions']
        break

# 戦闘時間リスト初期化
fight_times = [[] for p in range(len(phases))]

# 集計対象BOSS IDが設定されている戦闘IDのリストを抽出
target_fight_ids = [fight.get('id') for fight in fights_data['fights'] if fight.get('boss') == FFLOGS_TARGET_BOSS_ID]

# プレイヤー名を戦闘情報から取得
dps_table = { 'Total': Actor('Total', 'Total', len(phases)) }
for friendly in fights_data['friendlies']:
    # 対象の戦闘に参加しているプレイヤーか?
    in_target_fight = any([fight.get('id') for fight in friendly['fights'] if fight.get('id') in target_fight_ids])

    # 「対象の戦闘に参加」かつ「集計対象JOB」のプレイヤーをDPSテーブルに追加する
    if in_target_fight and friendly['type'] in JOB_SORT_RANK:
        dps_table[friendly['name']] = Actor(friendly['name'], friendly['type'], len(phases))

# プログレスバー初期化
with tqdm.tqdm(total=len(phases) * len(fights_data['fights'])) as pbar:

    # Google Chrome Driver Optionsの設定 for Headless mode
    options = webdriver.chrome.options.Options()
    options.add_argument('--headless')

    # Selenium Google Chrome Driver
    with webdriver.Chrome(options=options) as driver:
        for p in range(1, len(phases) + 1):
            if p not in intermissions:
                driver.get(FFLOGS_DPS_URL.format(report_id=report_id, boss_id=FFLOGS_TARGET_BOSS_ID, phase_num=p))
                time.sleep(1.0)
                html_table = BeautifulSoup(driver.page_source.encode('utf-8'), 'html.parser').find('table', id='main-table-0')

                if html_table is None:
                    continue

                # 
                for row in html_table.find('tbody').find_all('tr'):
                    name_cell = row.find('td', {'class': 'report-table-name'})
                    dps_cell = row.find('td', {'class': 'primary', 'class': 'main-per-second-amount'})

                    if name_cell is None or dps_cell is None:
                        continue
                    
                    name_text = name_cell.get_text().replace('\n', '')
                    if name_text in dps_table:
                        dps_text = dps_cell.get_text().replace('\n', '').replace('\t', '').replace(',', '')
                        dps_table[name_text].dps[p - 1] = float(dps_text)
                    
                    total_dps_text = html_table.find('tfoot').find('tr').find_all('td')[3].get_text()
                    dps_table['Total'].dps[p - 1] = float(total_dps_text.replace('\n', '').replace('\t', '').replace(',', ''))

            for fight in fights_data['fights']:
                pbar.update()
                if fight['zoneID'] == FFLOGS_TARGET_ZONE_ID:
                    driver.get(FFLOGS_DPS_URL.format(report_id=report_id, boss_id=FFLOGS_TARGET_BOSS_ID, phase_num=p) + FFLOGS_URL_FIGHT_QUERY.format(fight_id=fight['id']))
                    time.sleep(0.4)
                    html_table = BeautifulSoup(driver.page_source.encode('utf-8'), 'html.parser').find('table', id='main-table-0')

                    if html_table is None:
                        continue

                    active_time_text = html_table.find('tfoot').find('tr').find_all('td')[2].get_text()
                    active_time = float(active_time_text.replace('s', '').replace('\n', '').replace(',', ''))
                    if active_time > 0.0:
                        fight_times[p - 1].append(active_time)

# DPSテーブルが空のプレイヤーを除外
for name in list(dps_table.keys()):
    if sum(dps_table[name].dps) == 0:
        del dps_table[name]

actor_list = list(dps_table.values())
actor_list.sort()

result_text =  '###################################\n' \
               ' Results\n' \
               '###################################\n'
for p in range(1, len(phases) + 1):
    for actor in actor_list:
        result_text += str(actor.dps[p - 1]) + '\t'
    if len(fight_times[p - 1]) > 0:
        result_text += str(max(fight_times[p - 1]) ) + '\t' + str(mean(fight_times[p - 1])) + '\n'
    else:
        result_text += '\t\n'

print(result_text)
