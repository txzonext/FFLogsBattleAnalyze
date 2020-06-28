import configparser
import datetime
import os
import time

import requests
import tqdm
from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver import ChromeOptions
from selenium.webdriver.common.by import By
from selenium.webdriver.support import expected_conditions as EC
from selenium.webdriver.support.ui import WebDriverWait
from webdriverdownloader import ChromeDriverDownloader

config = configparser.ConfigParser()
config.read('settings.ini', encoding='utf-8')

# ソート用ジョブ名配列
JOB_SORT_RANK = [
    'DarkKnight', 'Warrior', 'Gunbreaker', 'Paladin', 'WhiteMage',
    'Astrologian', 'Scholar', 'Samurai', 'Monk', 'Dragoon', 'Ninja', 'Bard',
    'Machinist', 'Dancer', 'BlackMage', 'Summoner', 'RedMage', 'Total']

FFLOGS_TARGET_ZONE_ID = 887   # The Epic of Alexander
FFLOGS_TARGET_BOSS_ID = 1050  # The Epic of Alexander
FFLOGS_API_FIGHT_URL = (
    'https://www.fflogs.com/v1/report/fights/{report_id}?api_key={api_key}'
)
FFLOGS_DPS_URL = (
    'https://www.fflogs.com/reports/{report_id}/#boss={boss_id}&difficulty=100'
)
FFLOGS_URL_DAMAGE_DONE_AND_PHASE_QUERY = '&type=damage-done&phase={phase_num}'
FFLOGS_URL_FIGHT_QUERY = '&fight={fight_id}'

base_dir = os.path.dirname(os.path.abspath(__file__))
bin_dir = os.sep.join([base_dir, 'bin'])
ChromeDriverDownloader(download_root=base_dir, link_path=bin_dir) \
    .download_and_install()
os.environ['PATH'] = os.pathsep.join([bin_dir, os.environ.get('PATH', '')])


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


def get_analysys_result2(api_key: str, report_id: str) -> str:
    '''
    analyze: 対象のレポートを分析する\n
    param report_id: 対象のFFLogs レポートID\n
    return: プレイヤー、フェーズ単位の分析結果(タブ区切り文字)
    '''
    # FFLogs APIから戦闘情報を取得
    res = requests.get(FFLOGS_API_FIGHT_URL.format(
        report_id=report_id, api_key=api_key))
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
    target_fight_ids = [
        fight.get('id') for fight in fights_data['fights']
        if fight.get('boss') == FFLOGS_TARGET_BOSS_ID
    ]

    # プレイヤー名を戦闘情報から取得
    dps_table = {'Total': Actor('Total', 'Total', len(phases))}
    for friendly in fights_data['friendlies']:
        # 対象の戦闘に参加しているプレイヤーか?
        in_target_fight = any(
            [
                fight.get('id') for fight in friendly['fights']
                if fight.get('id') in target_fight_ids
            ]
        )

        # 「対象の戦闘に参加」かつ「集計対象JOB」のプレイヤーをDPSテーブルに追加する
        if in_target_fight and friendly['type'] in JOB_SORT_RANK:
            dps_table[friendly['name']] = Actor(
                friendly['name'], friendly['type'], len(phases))

    options = ChromeOptions()
    options.add_argument('--no-sandbox')

    # プログレスバー初期化
    with tqdm.tqdm(total=len(phases) * len(fights_data['fights'])) as pbar:

        with webdriver.Chrome(options=options) as driver:
            # フェーズ単位処理
            for p in range(1, len(phases) + 1):
                # 各フェーズのDPS値取得
                if p not in intermissions:
                    driver.get(
                        FFLOGS_DPS_URL.format(
                            report_id=report_id,
                            boss_id=FFLOGS_TARGET_BOSS_ID
                        ) +
                        FFLOGS_URL_DAMAGE_DONE_AND_PHASE_QUERY.format(
                            phase_num=p
                        )
                    )
                    WebDriverWait(driver, 30).until(
                        EC.presence_of_element_located((By.ID, 'main-table-0')))
                    time.sleep(1.0)
                    html_table = BeautifulSoup(driver.page_source.encode(
                        'utf-8'), 'html.parser').find('table', id='main-table-0')
                    driver.back()

                    if html_table is None:
                        continue

                    for row in html_table.find('tbody').find_all('tr'):
                        name_cell = row.find(
                            'td', {'class': 'report-table-name'})
                        dps_cell = row.find(
                            'td', {'class': 'primary', 'class': 'main-per-second-amount'})

                        if name_cell is None or dps_cell is None:
                            continue

                        name_text = name_cell.get_text().replace('\n', '')
                        if name_text in dps_table:
                            dps_text = dps_cell.get_text().replace(
                                '\n', '').replace('\t', '').replace(',', '')
                            dps_table[name_text].dps[p - 1] = float(dps_text)

                        total_dps_text = (
                            html_table
                            .find('tfoot')
                            .find('tr')
                            .find_all('td')[3]
                            .get_text())
                        dps_table['Total'].dps[p - 1] = (
                            float(
                                total_dps_text
                                .replace('\n', '')
                                .replace('\t', '')
                                .replace(',', '')
                            )
                        )

                # 各フェーズ・戦闘単位の戦闘時間取得
                for fight in fights_data['fights']:
                    pbar.update()
                    if fight['zoneID'] == FFLOGS_TARGET_ZONE_ID:
                        driver.get(
                            FFLOGS_DPS_URL.format(
                                report_id=report_id,
                                boss_id=FFLOGS_TARGET_BOSS_ID
                            )
                            + FFLOGS_URL_DAMAGE_DONE_AND_PHASE_QUERY
                            .format(phase_num=p)
                            + FFLOGS_URL_FIGHT_QUERY
                            .format(fight_id=fight['id'])
                        )
                        WebDriverWait(driver, 30).until(
                            EC.presence_of_element_located((By.ID, 'main-table-0')))
                        time.sleep(0.5)
                        html_table = BeautifulSoup(
                            driver.page_source.encode('utf-8'),
                            'html.parser'
                        ).find('table', id='main-table-0')
                        driver.back()

                        if html_table is None:
                            continue

                        active_time_text = html_table.find('tfoot').find(
                            'tr').find_all('td')[2].get_text()
                        active_time = float(active_time_text.replace(
                            's', '').replace('\n', '').replace(',', ''))
                        if active_time >= 0.0:
                            fight_times[p - 1].append(active_time)

    # DPSテーブルが空のプレイヤーを除外
    for name in list(dps_table.keys()):
        if sum(dps_table[name].dps) == 0:
            del dps_table[name]

    actor_list = list(dps_table.values())
    actor_list.sort()

    result_text = ''
    count = 0
    repo_start = fights_data["start"]
    alex_start = fights_data["fights"][0]["start_time"]
    alex_end = fights_data["fights"][len(
        fights_data["fights"]) - 1]["end_time"]
    dt1 = datetime.datetime.fromtimestamp((repo_start + alex_start)/1000)
    dt2 = datetime.datetime.fromtimestamp((repo_start + alex_end)/1000)
    result_text += "start -->  " + \
        str(dt1) + '\n' + "end   -->  " + str(dt2) + '\n'
    for ftime in fight_times:
        count = count + 1
        result_text += "ph." + str(count) + '\t'
        for ft in ftime:
            result_text += str(ft) + '\t'
        result_text += '\n'
#    for p in range(1, len(phases) + 1):
#        for actor in actor_list:
#            result_text += str(actor.dps[p - 1]) + '\t'
#        if len(fight_times[p - 1]) > 0:
#            result_text += str(max(fight_times[p - 1]) ) + '\t' + str(mean(fight_times[p - 1])) + '\n'
#        else:
#            result_text += '\t\n'

    return result_text
