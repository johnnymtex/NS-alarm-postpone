import requests
import json
import os
import dropbox

from requests.auth import HTTPBasicAuth
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

def get_stations():
    url = "https://gateway.apiportal.ns.nl/nsapp-stations/v2/?countryCodes='NL'"

    try:
        response = requests.get(
            url,
            headers={'Ocp-Apim-Subscription-Key': os.environ['NS_API_PRIMARY_KEY']},
            auth=HTTPBasicAuth(os.environ['NS_API_USERNAME'], os.environ['NS_API_PASSWORD']),
            timeout=10
        )

        return response.json()
    
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to connect to the API: {e}")
    
def find_station_code(stations, long_name):
    matched_station = next((s for s in stations['payload'] if s['namen']['lang'] == long_name), None)

    if matched_station:
       print('UIC Code:', matched_station['UICCode'])
       return matched_station['UICCode']
    else:
       print('Station not found!')

def get_departures(departure_code, arrival_code, start_datetime, end_datetime=None):
    url = f'https://gateway.apiportal.ns.nl/reisinformatie-api/api/v3/trips?originUicCode={departure_code}&destinationUicCode={arrival_code}&dateTime={start_datetime}'

    try:
        response = requests.get(
            url,
            headers={'Ocp-Apim-Subscription-Key': os.environ['NS_API_PRIMARY_KEY']},
            auth=HTTPBasicAuth(os.environ['NS_API_USERNAME'], os.environ['NS_API_PASSWORD']),
        )
    except requests.RequestException as e:
        raise ConnectionError(f"Failed to connect to the API: {e}")
    
    trips = response.json().get('trips', [])
    filtered_trips = [trip for trip in trips if trip.get('legs') and any(
        (leg.get('product', {}).get('longCategoryName') == "Intercity direct") or (leg.get('product', {}).get('longCategoryName') == "Eurocity Direct") for leg in trip['legs']
    )]

    return filtered_trips

def write_dbox(text):
    dbx = dropbox.Dropbox(os.getenv('DROPBOX_ACCESS_TOKEN'))

    with open('train.txt', 'w') as file_out:
        file_out.write(text)
    
    with open('train.txt', 'rb') as file_in:
        dbx.files_upload(file_in.read(), '/train.txt', mode=dropbox.files.WriteMode.overwrite)


stations = get_stations()
departure_code = find_station_code(stations, 'Eindhoven Centraal')
arrival_code = find_station_code(stations, 'Rotterdam Centraal')

time_shifts=[timedelta(minutes=0), timedelta(minutes=15), timedelta(minutes=30), timedelta(minutes=45), 
             timedelta(minutes=60), timedelta(minutes=75), timedelta(minutes=90), timedelta(minutes=105)]

possible_trains = []

today = date.today()

for shift in time_shifts:
    start_time = datetime(today.year, today.month, today.day, 7, 0, 0, tzinfo=ZoneInfo("Europe/Amsterdam")) + shift
    start_time = start_time.isoformat()

    list_dep = get_departures(departure_code, arrival_code, start_time)

    seen_times = {t['legs'][0]['origin']['plannedDateTime'] for t in possible_trains}
    
    for train in list_dep:
        planned_time = train['legs'][0]['origin']['plannedDateTime']
        if planned_time not in seen_times:
            possible_trains.append(train)
            seen_times.add(planned_time)

count_cancels = 0

for train in possible_trains:
    if train['status']=='CANCELLED':
        count_cancels += 1

print(count_cancels)

if count_cancels >= 1:
    write_dbox('cancel')
else:
    write_dbox('keep')