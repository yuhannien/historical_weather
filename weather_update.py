# %%
import pandas as pd
from requests import get,post
import json
from dateutil.parser import parse
import io
from collections import OrderedDict
from datetime import datetime, timedelta
import os

# %%
import argparse
parser = argparse.ArgumentParser()
parser.add_argument("-t",
                    "--type",
                    type=str,
                    default="daily",
                    help="Type of data to be retrieved: daily or hourly")

parser.add_argument("-a",
                    "--all",
                    type=str,
                    default=False,
                    help="If true, all years will be retrieved")

parser.add_argument("-o",
                    "--overwrite", 
                    type=str,
                    default=True,
                    help="If true, existing files will be overwritten")

#jupyter會傳一個-f進來，不這樣接會有錯誤
args, unknown = parser.parse_known_args()
ALL = args.all
OVERWRITE = args.overwrite
TYPE = args.type
assert TYPE in ["daily", "hourly"], "Type must be either daily or hourly"

# %%
my_headers = {    
    "accept": "application/json, text/javascript, */*; q=0.01",
    "accept-language": "ja-JP,ja;q=0.9,zh-TW;q=0.8,zh;q=0.7,en-US;q=0.6,en;q=0.5",
    "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
    "sec-ch-ua": "\"Chromium\";v=\"92\", \" Not A;Brand\";v=\"99\", \"Google Chrome\";v=\"92\"",
    "sec-ch-ua-mobile": "?0",
    "sec-fetch-dest": "empty",
    "sec-fetch-mode": "cors",
    "sec-fetch-site": "same-origin",
    "x-requested-with": "XMLHttpRequest", #required
}

# %%
def dictToGET(d):
    return '&'.join(['{}={}'.format(k,v) for k,v in d.items()])
def agr_get_items (station = '466910', type = 'hourly'): #check available fields
    if type == 'daily':
        get_items_URI = "https://agr.cwb.gov.tw/NAGR/history/station_day/get_items"
    elif type == 'hourly':
        get_items_URI = "https://agr.cwb.gov.tw/NAGR/history/station_hour/get_items"
    r = post(get_items_URI, data = {'station': station},  headers= my_headers)
    i = json.loads(r.text)
    d = {t['item']: t['cname'] for t in i['items']}
    if d == {}:
        return {}
    orderedD = OrderedDict()
    for e in i['columns']:
        orderedD[d[e]] = e 
    return orderedD
    try:
        return {t['cname']: t['item'] for t in i['items']}
    except:
        return r.text
def replaceListByDict(l, d):
    d['觀測時間'] = 'date'
    return [d[i] if i in d else i for i in l]

# %%
def getDataByCsvAPI(STA = '466900', start_time='2020-08-16', end_time='2020-09-13', type='hourly', save_path = ''):
    #print("Downloading data from {} to {}".format(start_time, end_time))
    #STA = '466900'
    if type=='hourly':
        URI = 'https://agr.cwb.gov.tw/NAGR/history/station_hour/create_report'     
    elif type=='daily':
        URI = 'https://agr.cwb.gov.tw/NAGR/history/station_day/create_report'
    items = agr_get_items(STA, type)
    data = {
        'station': STA,
        'start_time': parse(start_time).strftime('%Y-%m-%d'),
        'end_time': parse(end_time).strftime('%Y-%m-%d'),
        'items': ','.join(items.values()),
        'report_type':'csv_time',
        'level': '自動站'
    }
    if STA[0:2] not in ['46','C0','C1']:
        data['level'] = ''
    try:
        r = get(URI+'?'+dictToGET(data))
        r.encoding='big5'
        rio = io.StringIO(r.text)
        df = pd.read_csv(rio,encoding='big5', skiprows=[0], on_bad_lines = 'skip')
        df.columns = replaceListByDict(df.columns, items)
        df.drop(['測站代碼'], axis=1, inplace=True)
        df['date'] = pd.to_datetime(df['date'])
        df['date'] = df['date'].apply(add_2359)
    except Exception as e:
        print(e)
        return pd.DataFrame()
    if save_path != '':
        if os.path.exists(save_path) and not OVERWRITE:
            print("File already exists. Skipping...")
            return pd.DataFrame()
        df.to_csv(save_path, index=False)
        print ("Saved to {}".format(save_path))
    return df
def add_2359(d):
    if d.strftime('%H%M') == '2359':
        return d + pd.Timedelta(minutes=1)
    else:
        return d

# %%
def agr_get_sta_list(area_id=0, level_id=0):
    my_headers = {    
        "accept": "application/json, text/javascript, */*; q=0.01",
        "accept-language": "ja-JP,ja;q=0.9,zh-TW;q=0.8,zh;q=0.7,en-US;q=0.6,en;q=0.5",
        "content-type": "application/x-www-form-urlencoded; charset=UTF-8",
        "sec-ch-ua": "\"Chromium\";v=\"92\", \" Not A;Brand\";v=\"99\", \"Google Chrome\";v=\"92\"",
        "sec-ch-ua-mobile": "?0",
        "sec-fetch-dest": "empty",
        "sec-fetch-mode": "cors",
        "sec-fetch-site": "same-origin",
        "x-requested-with": "XMLHttpRequest", #required
    }
    URI = 'https://agr.cwb.gov.tw/NAGR/history/station_day/get_station_name'
    area = ['', '北', '中', '南', '東'][area_id]
    level = ['自動站', '新農業站'][level_id]
    r1 = post(URI, data={'area':area, 'level':level}, headers = my_headers)
    sta_dict = json.loads(r1.text)
    df = pd.DataFrame(sta_dict)
    extract_df = df[['ID', 'Cname', 'Altitude', 'Latitude_WGS84', 'Longitude_WGS84', 'Address', 'StnBeginTime', 'stnendtime', 'stationlist_auto']]
    extract_df.columns=['站號', '站名', '海拔高度(m)', '緯度', '經度', '地址', '資料起始日期', '撤站日期', '備註']
    return extract_df
def load_weather_station_list(include_suspended = False, include_agr_sta = True):
    #load from CWB
    raw = pd.read_html('https://e-service.cwb.gov.tw/wdps/obs/state.htm')
    weather_station_list = raw[0]
    if include_suspended:
        weather_station_list =  pd.concat([weather_station_list, raw[1]], ignore_index = True)
    #load from agri
    if include_agr_sta:
        weather_station_list = pd.concat([weather_station_list, agr_get_sta_list(level_id = 1)], ignore_index = True)
    return weather_station_list

# %%
sta_list = load_weather_station_list(include_suspended = True)
print('Weather station list downloaded')
#Problematic data (sta_no='466920',start_date='2022-03-15',end_date='2022-04-20')

# %%
import concurrent.futures
with concurrent.futures.ThreadPoolExecutor(max_workers=10) as executor:
    futures = []
    for index, row in sta_list[:].iterrows():
        os.makedirs('./data/'+row['站號'], exist_ok=True)
        #Define year range
        if ALL:
            try:
                years = range(int(row['資料起始日期'][0:4]),parse(row['撤站日期']).year+1)
            except:
                years = range(int(row['資料起始日期'][0:4]),datetime.today().year+1)
        else:
            try:
                #IF there is end date, skip this station
                parse(row['撤站日期'])
                years = []
            except:
                years = [datetime.today().year]
        #loop over years
        for year in years:
            print(row['站號'], year)
            try:
                if TYPE == 'hourly':
                    futures.append(executor.submit(getDataByCsvAPI, 
                                    row['站號'], 
                                    str(year)+'-01-01', 
                                    str(year)+'-12-31', 
                                    'hourly',
                                    './data/{}/{}_{}.csv'.format(row['站號'],row['站號'], year)
                                    ))
                elif TYPE == 'daily':
                    futures.append(executor.submit(getDataByCsvAPI, 
                                    row['站號'], 
                                    str(year)+'-01-01', 
                                    str(year)+'-12-31', 
                                    'daily',
                                    './data/{}/{}_{}_daily.csv'.format(row['站號'],row['站號'], year)
                                    ))
            except:
                print('Error')
                continue
            if index % 10 == 0:
                for future in futures:
                    future.result()

# %%



