#Load data to CSV

#For this project, we only need nflverse data. We use:
#1. Injury Status
#2. Weather
#3. Opponent defense strength (which we calculate)
#4. Betting Lines
#5. Stats (Of which we include all but current game)

#We use data from 2016 on
#2016/17-2024/25 is used for training
#2025/26 will be used for testing

#Imports
import nflreadpy as nfldata
import polars as pl
from pathlib import Path
from datetime import date

#Load Functions from nflreadpy
load_injuries = nfldata.load_injuries
load_schedule = nfldata.load_schedules
load_roster = nfldata.load_rosters_weekly
#Map sources to functions for ease of access
source_map = {
    "injury": load_injuries,
    "schedules": load_schedule,
    "rosters": load_roster,
}

#Downloads data given source and seasons
def download(source:str, seasons:list[int], force=False):
    if source in source_map:
        function = source_map.get(source)
        for i in seasons:
            currentdir = Path.cwd()
            targetdir = currentdir.parent.parent / "data" / "raw" / f"{source}_{i}.csv"
            if targetdir.exists():
                print(f"{source} {i} data already downloaded.")
                if !force:
                    print("Skipped")
                else:
                    targetdir.parent.mkdir(parents = True, exist_ok = True)
                    rawdf = function(i)
                    rawdf.write_csv(targetdir)
            else:
                targetdir.parent.mkdir(parents = True, exist_ok = True)
                rawdf = function(i)
                rawdf.write_csv(targetdir)
    else:
        raise ValueError(f"Source not in Source Directory. Current Source Directory: {source_map.keys()}")

#Refreshes Current Season, Currently 2026/27
def refresh26(source:str):
    if source in source_map:
        function = source_map.get(source)
        currentdir = Path.cwd()
        targetdir = currentdir.parent.parent / "data" / "raw" / f"{source}_2026.csv"
        targetdir.parent.mkdir(parents = True, exist_ok = True)
        rawdf = function(2026)
        rawdf.write_csv(targetdir)
    else:
        raise ValueError(f"Source not in Source Directory. Current Source Directory: {source_map.keys()}")
def printlastdownload():
    print(f"Current data last downloaded {last26download}")


#Loads data back from csv to pandas df
def loadtodf(source:str, seasons:list[int]):
    if source in source_map:
        function = source_map.get(source)
        for i in seasons:
            currentdir = Path.cwd()
            targetdir = currentdir.parent.parent / "data" / "raw" / f"{source}_{i}.csv"
            if !targetdir.exists():
                raise RuntimeError(f"File not found. Check for download")
            else:
                
    else:
        raise KeyError(f"Source not in Source Directory. Current Source Directory: {source_map.keys()}")



#FIXES AND WIP
#Fix File Pathing
#Create Helper Functions for repeated code
#Fix lastdownloaded Tracking
#Make refresh function generalizable