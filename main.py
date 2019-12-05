import sys, time, os, json, array, requests, tqdm
from selenium import webdriver
from statistics import mean
from bs4 import BeautifulSoup
from selenium.webdriver.chrome.options import Options
import chromedriver_binary

# ソート用ジョブ名配列
JOB_SORT_RANK = ['DarkKnight', 'Warrior', 'Gunbreaker', 'Paladin', 'WhiteMage', 'Astrologian', 'Scholar', 'Samurai', 'Monk', 'Dragoon', 'Ninja', 'Bard', 'Machinist', 'Dancer', 'BlackMage', 'Summoner', 'RedMage', 'Total']

FFLOGS_TARGET_ZONE_ID = 887  # The Epic of Alexander
FFLOGS_TARGET_BOSS_ID = 1050 # The Epic of Alexander
FFLOGS_API_FIGHT_URL = 'https://www.fflogs.com/v1/report/fights/{report_id}?api_key={api_key}'
FFLOGS_DPS_URL = 'https://www.fflogs.com/reports/{report_id}#boss={boss_id}&difficulty=100&type=damage-done&phase={phase_num}'
FFLOGS_URL_FIGHT_QUERY = '&fight={fight_id}'

FFLOGS_API_KEY = ''
# FFLogs APIキー

class Actor:
	def __init__(self, name, job, phase_count):
		self.name = name
		self.job = job
		self.dps = [0] * phase_count

	def __lt__(self, other):
		# self < other
		return JOB_SORT_RANK.index(self.job) < JOB_SORT_RANK.index(other.job)

	def __repr__(self):
		return self.name + ': ' + str(self.dps)

if sys.argv[1].startswith('https://') and 'fflogs.com/reports/' in sys.argv[1]:
	report_id = sys.argv[1].split('/')[4]
else:
	report_id = sys.argv[1]

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

# プログレスバー初期化
pbar = tqdm.tqdm(total=len(phases) * len(fights_data['fights']))

# プレイヤー名を戦闘情報から取得
dps_table = { 'Total': Actor('Total', 'Total', len(phases)) }
for friendly in fights_data['friendlies']:
	if friendly['type'] in JOB_SORT_RANK:
		dps_table[friendly['name']] = Actor(friendly['name'], friendly['type'], len(phases))

# Selenium Google Chrome Driver
options = Options()
options.add_argument('--headless')
driver = webdriver.Chrome(options=options)

fight_times = []
for i in range(1, len(phases) + 1):
	if i not in intermissions:
		driver.get(FFLOGS_DPS_URL.format(report_id=report_id, boss_id=FFLOGS_TARGET_BOSS_ID, phase_num=i))
		time.sleep(1.0)
		html_table = BeautifulSoup(driver.page_source.encode('utf-8'), 'html.parser').find('table', id='main-table-0')

		if html_table is None:
			continue

		for row in html_table.find('tbody').find_all('tr'):
			name_cell = row.find('td', {'class': 'report-table-name'})
			dps_cell = row.find('td', {'class': 'primary', 'class': 'main-per-second-amount'})

			if name_cell is None or dps_cell is None:
				continue
			
			name_text = name_cell.get_text().replace('\n', '')
			if name_text in dps_table:
				dps_text = dps_cell.get_text().replace('\n', '').replace('\t', '').replace(',', '')
				dps_table[name_text].dps[i - 1] = float(dps_text)
			
			total_dps_text = html_table.find('tfoot').find('tr').find_all('td')[3].get_text()
			dps_table['Total'].dps[i - 1] = float(total_dps_text.replace('\n', '').replace('\t', '').replace(',', ''))

	fight_times.append([])
	for fight in fights_data['fights']:
		pbar.update()
		if fight['zoneID'] == FFLOGS_TARGET_ZONE_ID:
			driver.get(FFLOGS_DPS_URL.format(report_id=report_id, boss_id=FFLOGS_TARGET_BOSS_ID, phase_num=i) + FFLOGS_URL_FIGHT_QUERY.format(fight_id=fight['id']))
			time.sleep(0.4)
			html_table = BeautifulSoup(driver.page_source.encode('utf-8'), 'html.parser').find('table', id='main-table-0')

			if html_table is None:
				continue

			active_time_text = html_table.find('tfoot').find('tr').find_all('td')[2].get_text()
			active_time = float(active_time_text.replace('s', '').replace('\n', '').replace(',', ''))
			if active_time > 0.0:
				fight_times[i - 1].append(active_time)

pbar.close()
driver.close()

# DPSテーブルが空のプレイヤーを除外
for name in list(dps_table.keys()):
	if sum(dps_table[name].dps) == 0:
		del dps_table[name]

print('###################################')
print(' Results')
print('###################################')
actor_list = list(dps_table.values())
actor_list.sort()

result_text = ''
for i in range(1, len(phases) + 1):
	for actor in actor_list:
		result_text += str(actor.dps[i - 1]) + '\t'
	if len(fight_times[i - 1]) > 0:
		result_text += str(max(fight_times[i - 1]) ) + '\t' + str(mean(fight_times[i - 1])) + '\n'
	else:
		result_text += '\t\n'

print(result_text)