#imports
from pointsprojection import clean
import numpy as np
import pandas as pd


#Create filters for whether a player played and ordering games and making a key index
def createfilters():
    #load
    player_weeks = clean.load_player_weeks()
    #create gameorderkeys
    player_weeks['gameorderkey'] = player_weeks['season'] * 100 + player_weeks['week']
    #define players who have played in the week
    player_weeks['played'] = (player_weeks['offense_snaps'] >= 1) | (player_weeks['has_stats'] & ~ player_weeks['has_snap_row'])
    #sort by ids and keys to order by players and games
    player_weeks = player_weeks.sort_values(by=['gsis_id', 'gameorderkey'])
    #reset the df to index by sorted
    player_weeks = player_weeks.reset_index(drop=True)
    return player_weeks

#Feature column creation func
def createfeatures(player_weeks):
    #Filter by played to build features on
    played_rows = player_weeks[player_weeks['played']].copy()
    grouped_rows = played_rows.groupby('gsis_id')

    #GROUP 1 FEATURES(Simple Rollers)
    #build ppr points rolling average
    player_weeks['ppr_last3_mean'] = grouped_rows['fantasy_points_ppr'].transform(lambda x: x.rolling(window = 3, min_periods = 1).mean())
    player_weeks['ppr_last5_mean'] = grouped_rows['fantasy_points_ppr'].transform(lambda x: x.rolling(window = 5, min_periods = 1).mean())
    player_weeks['ppr_last8_mean'] = grouped_rows['fantasy_points_ppr'].transform(lambda x: x.rolling(window = 8, min_periods = 1).mean())
    #Build existent games
    player_weeks['ppr_last3_n'] = grouped_rows['fantasy_points_ppr'].transform(lambda x: x.rolling(window = 3, min_periods = 1).count())
    player_weeks['ppr_last5_n'] = grouped_rows['fantasy_points_ppr'].transform(lambda x: x.rolling(window = 5, min_periods = 1).count())
    player_weeks['ppr_last8_n'] = grouped_rows['fantasy_points_ppr'].transform(lambda x: x.rolling(window = 8, min_periods = 1).count())
    #build exponentially weighted mean with half life = 3
    player_weeks['ppr_ewm'] = grouped_rows['fantasy_points_ppr'].transform(lambda x: x.ewm(halflife = 3).mean())
    #build standard deviation
    player_weeks['ppr_last8_std'] = grouped_rows['fantasy_points_ppr'].transform(lambda x: x.rolling(window = 8, min_periods = 3).std())
    #build career stats
    player_weeks['ppr_career_mean'] = grouped_rows['fantasy_points_ppr'].transform(lambda x: x.expanding().mean())
    #Define what columns need lagging and forward filling
    columnlist = ['ppr_last3_mean', 'ppr_last5_mean', 'ppr_last8_mean', 'ppr_last3_n', 'ppr_last5_n', 'ppr_last8_n', 'ppr_ewm', 'ppr_last8_std', 'ppr_career_mean']
    countcolumns = ['ppr_last3_n', 'ppr_last5_n', 'ppr_last8_n']
    #Lag features and forward fill necessary
    player_weeks = lagfeatures(player_weeks, columnlist, countcolumns)


    #GROUP 1 FEATURES(Season Scoped)
    grouped_seasons = played_rows.groupby(['gsis_id','season'])
    player_weeks['games_played_this_season'] = grouped_seasons.cumcount() + 1
    player_weeks['ppr_season_mean'] = grouped_seasons['fantasy_points_ppr'].transform(lambda x: x.expanding().mean())
    player_weeks = priorseasonfeatures(player_weeks)
    player_weeks = lagfeatures(player_weeks, ['games_played_this_season', 'ppr_season_mean'], ['games_played_this_season'], by = ['gsis_id', 'season'])


    
    return player_weeks

def lagfeatures (player_weeks, columns, count_columns = None, by = ['gsis_id']):
    #Group by id
    grouped_weeks = player_weeks.groupby(by)[columns]
    #Shift and forward fill
    player_weeks[columns] = grouped_weeks.shift(1)
    player_weeks[columns] = player_weeks.groupby(by)[columns].ffill()

    #fill nan for necessary columns
    if count_columns:
        player_weeks[count_columns] = player_weeks[count_columns].fillna(0)
    return player_weeks

def priorseasonfeatures(player_weeks):
    played_rows = player_weeks[player_weeks['played']]
    season_summary = (
        played_rows.groupby(['gsis_id', 'season'], as_index=False)
        .agg(ppr_prior_season_mean=('fantasy_points_ppr','mean'),
            prior_season_games = ('fantasy_points_ppr','size'))
    )

    season_summary['season'] = season_summary['season'] + 1

    player_weeks = player_weeks.drop(columns=['ppr_prior_season_mean', 'prior_season_games'], errors='ignore')
    player_weeks = player_weeks.merge(season_summary, on=['gsis_id','season'], how='left')

    player_weeks['prior_season_games'] = player_weeks['prior_season_games'].fillna(0)
    return player_weeks