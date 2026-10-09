#Load data to CSV

#For this project, we only need nflverse data. We use:
#1. Injury Status
#2. Weather
#3. Opponent defense strength (which we calculate)
#4. Betting Lines
#5. Stats (Of which we include all but current game)

#We use data from 2016 on
#2015/16 is used historically for initial 2016 weeks
#2016/17-2024/25 is used for training
#2025/26 will be used for testing

#Imports
import nflreadpy as nfldata
from pathlib import Path
import pandas as pd
from datetime import datetime
from functools import partial

#Map sources to functions for ease of access
source_map = {
    "injury": nfldata.load_injuries,
    "schedules": nfldata.load_schedules,
    "rosters": nfldata.load_rosters_weekly,
    "playbyplay": nfldata.load_pbp,
    "snapcounts": nfldata.load_snap_counts,
    "playerstats": nfldata.load_player_stats,
    "ngs_receiving": partial(nfldata.load_nextgen_stats, stat_type="receiving"),
    "ngs_passing": partial(nfldata.load_nextgen_stats, stat_type="passing"),
    "ngs_rushing": partial(nfldata.load_nextgen_stats, stat_type="rushing"),
}

#Fix the messy pathing and make it consistent over all file systems
this_path = Path(__file__).resolve()
ROOT_DIR = next(p for p in this_path.parents if (p/".git").exists())
RAW_DIR = ROOT_DIR/"data"/"raw"
PROC_DIR = ROOT_DIR/"data"/"processed"

def validatesource (source:str):
    if source not in source_map:
        raise ValueError(f"Source not in Source Directory. Current Source Directory: {source_map.keys()}")

def getpath (source:str, season:int):
    validatesource(source)
    return RAW_DIR / f"{source}" / f"{source}_{season}.csv"

def writetocsv(file_path, function, season):
    file_path.parent.mkdir(parents = True, exist_ok = True)
    rawdf = function(season)
    rawdf.write_csv(file_path)

#Downloads data given source and seasons
def download(source:str, seasons:list[int], force=False):
    validatesource(source)
    function = source_map[source]
    for i in seasons:
        file_path = getpath(source, i)
        if i < 2016 and "ngs" in source:
            continue
        if file_path.exists() and not force:
            print(f"{source} {i} data already downloaded. Not Forcing, Skipped")
        else:
            writetocsv(file_path, function, i)
    
#Refreshes Current Season, Currently 2026/27
def refreshseason(source:str, season:int):
    download(source, [season], force=True)

def printlastdownload(source, season):
    path = getpath(source, season)
    mtime_timestamp = path.stat().st_mtime
    lastdownload = datetime.fromtimestamp(mtime_timestamp)
    print(f"Current data last downloaded {lastdownload}")


#Loads data back from csv to pandas df
def loadtodf(source: str, seasons: list[int], parse_dates: list[str] | None = None) -> pd.DataFrame:
    validatesource(source)
    frames = []
    for i in seasons:
        file_path = getpath(source, i)
        if i < 2016 and "ngs" in source:
            continue
        if not file_path.exists():
            raise FileNotFoundError(
                f"No {source} data for {i} at {file_path}. Run download('{source}', [{i}]) first."
            )
        frames.append(pd.read_csv(file_path, parse_dates=parse_dates, low_memory=False))
    return pd.concat(frames, ignore_index=True)