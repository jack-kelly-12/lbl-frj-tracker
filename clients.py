import pandas as pd
from pybaseball import playerid_lookup

INDIVIDUAL_CLIENTS = [
    ("Buxton", "Byron"),
    ("Polanco", "Jorge"),
    ("Arraez", "Luis"),
    ("Benson", "Will"),
    ("Sanchez", "Gary"),
    ("Vazquez", "Christian"),
    ("Horwitz", "Spencer"),
]

CLIENT_TEAMS = ["SD", "KC"]


def get_client_players() -> pd.DataFrame:
    rows = []
    for last, first in INDIVIDUAL_CLIENTS:
        result = playerid_lookup(last, first, fuzzy=True)
        if not result.empty:
            result['mlb_played_last'] = pd.to_numeric(result['mlb_played_last'], errors='coerce')
            row = result.dropna(subset=['mlb_played_last']).sort_values("mlb_played_last", ascending=False).iloc[0]
            rows.append({"name": f"{first} {last}", "mlbam_id": int(row["key_mlbam"])})
    return pd.DataFrame(rows, columns=["name", "mlbam_id"])
