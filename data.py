import logging
from datetime import datetime, timedelta

import pandas as pd
import requests
from bs4 import BeautifulSoup
from pybaseball import statcast

from clients import CLIENT_TEAMS

logger = logging.getLogger(__name__)

COLUMNS = ['batter_name', 'playId', 'batter', 'launch_speed', 'launch_angle', 'events']
URL_FANGRAPHS = "https://www.fangraphs.com/guts.aspx?type=cn"


def is_client(df: pd.DataFrame, client_ids: list) -> pd.Series:
    on_client_team = (
        ((df['inning_topbot'] == 'Top') & df['away_team'].isin(CLIENT_TEAMS)) |
        ((df['inning_topbot'] == 'Bot') & df['home_team'].isin(CLIENT_TEAMS))
    )
    return df['batter'].isin(client_ids) | on_client_team


def get_play_by_play(game_id):
    url = f"https://statsapi.mlb.com/api/v1/game/{game_id}/playByPlay"
    response = requests.get(url)
    if response.status_code == 200:
        return response.json()
    logger.warning(f"Failed to fetch play-by-play for game {game_id}")
    return None


def extract_play_ids(play_by_play, game):
    play_ids = []
    for play in play_by_play.get('allPlays', []):
        about = play.get('about', {})
        matchup = play.get('matchup', {})
        for event in play.get('playEvents', []):
            if event.get('isPitch') and 'playId' in event:
                play_ids.append({
                    'playId': event['playId'],
                    'pitch_number': event.get('pitchNumber'),
                    'game_pk': int(game),
                    'batter': matchup.get('batter', {}).get('id'),
                    'pitcher': matchup.get('pitcher', {}).get('id'),
                    'inning': about.get('inning'),
                    'inning_topbot': about.get('halfInning'),
                    'at_bat_number': about.get('atBatIndex', 0) + 1,
                })
    return play_ids


def process_games(games):
    all_play_ids = []
    for game in games:
        play_by_play = get_play_by_play(game)
        if play_by_play:
            all_play_ids.extend(extract_play_ids(play_by_play, game))
    return pd.DataFrame(all_play_ids)


def get_statcast():
    try:
        yesterday = (datetime.today() - timedelta(days=1)).strftime('%Y-%m-%d')
        sc = statcast(yesterday, yesterday)
        sc['game_date'] = pd.to_datetime(sc['game_date']).dt.date

        api = process_games(sc['game_pk'].unique())
        api['inning_topbot'] = api['inning_topbot'].replace({'top': 'Top', 'bottom': 'Bot'})

        sc = pd.merge(sc, api, how='left', on=[
            'game_pk', 'inning', 'inning_topbot', 'pitch_number', 'at_bat_number', 'batter', 'pitcher'
        ])
        logger.info("Statcast data fetched successfully.")
        return sc.drop_duplicates()
    except Exception as e:
        logger.error(f"Error fetching statcast data: {e}")
        return pd.DataFrame()


def get_player_names(player_ids) -> dict:
    ids_str = ','.join(str(int(i)) for i in player_ids if pd.notna(i))
    if not ids_str:
        return {}
    try:
        response = requests.get(
            "https://statsapi.mlb.com/api/v1/people",
            params={"personIds": ids_str},
        )
        response.raise_for_status()
        return {p['id']: p['fullName'] for p in response.json().get('people', [])}
    except Exception as e:
        logger.error(f"Failed to lookup player names: {e}")
        return {}


def get_yesterday_data() -> pd.DataFrame:
    sc = get_statcast()
    sc = sc[sc.description == 'hit_into_play'].copy()
    sc['launch_speed_adj'] = sc['launch_speed'] + 2
    sc['video'] = sc['playId'].apply(lambda x: f'https://baseballsavant.mlb.com/sporty-videos?playId={x}')
    sc['batter_name'] = sc['batter'].map(get_player_names(sc['batter'].unique())).fillna("-")
    return sc


def get_frjs(sc: pd.DataFrame, client_ids: list) -> pd.DataFrame:
    df = sc[sc['events'] == 'home_run']
    left_right = df[df['hit_location'].isin([7, 9]) & (df['hit_distance_sc'] <= 350)]
    center = df[(df['hit_location'] == 8) & (df['hit_distance_sc'] <= 380)]
    result = pd.concat([left_right, center])
    return result[is_client(result, client_ids)][COLUMNS]


def get_action_items(sc: pd.DataFrame, client_ids: list) -> pd.DataFrame:
    non_hr_events = ['single', 'double', 'triple', 'field_out', 'sacrifice_fly', 'sac_fly_double_play', 'field_error']
    df = sc[sc['events'].isin(non_hr_events)]
    left_right = df[df['hit_location'].isin([7, 9]) & (df['hit_distance_sc'] >= 365)]
    center = df[(df['hit_location'] == 8) & (df['hit_distance_sc'] >= 380)]
    result = pd.concat([left_right, center])
    return result[~is_client(result, client_ids)][COLUMNS]


def get_client_hrs(sc: pd.DataFrame, client_ids: list) -> pd.DataFrame:
    result = sc[sc['events'] == 'home_run']
    return result[is_client(result, client_ids)][COLUMNS]


def scrape_woba_weights(url: str = URL_FANGRAPHS) -> dict[str, float]:
    response = requests.get(url)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, 'html.parser')
    table = soup.find('table', {'class': 'rgMasterTable'})
    if not table:
        raise ValueError("Could not find wOBA weights table")

    row_2024 = next(
        (cells for row in table.find_all('tr')
         if (cells := row.find_all('td')) and cells[0].text.strip() == '2024'),
        None
    )
    if not row_2024:
        raise ValueError("No data found for the 2024 season")

    return {
        'single': float(row_2024[5].text.strip()),
        'double': float(row_2024[6].text.strip()),
        'triple': float(row_2024[7].text.strip()),
        'home_run': float(row_2024[8].text.strip()),
        'field_out': 0,
        'walk': float(row_2024[3].text.strip()),
        'hbp': float(row_2024[4].text.strip()),
    }
