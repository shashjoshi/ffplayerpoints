#imports
from pointsprojection import clean
import numpy as np
import pandas as pd


#Create filters for whether a player played and ordering games and making a key index
def createfilters():
    player_weeks = clean.load_player_weeks()
    player_weeks['gameorderkey'] = player_weeks['season'] * 100 + player_weeks['week']
    player_weeks['played'] = (player_weeks['offense_snaps'] >= 1) | (player_weeks['has_stats'] & ~ player_weeks['has_snap_row'])

def createfeatures():
    player_weeks = clean.load_player_weeks()
    #build ppr points rolling average
    player_weeks['ppr_last3_mean'] = player_weeks['fantasy_points_ppr'].rolling(window=3).mean()
    player_weeks['ppr_last5_mean'] = player_weeks['fantasy_points_ppr'].rolling(window=5).mean()
    player_weeks['ppr_last8_mean'] = player_weeks['fantasy_points_ppr'].rolling(window=8).mean()
    #build how many games exist in each window
    player_weeks['ppr_last3_n'] = 
    player_weeks['ppr_last5_n'] = 
    player_weeks['ppr_last8_n'] = 
    #build exponentially weighted mean, half life 3
    player_weeks['ppr_ewm'] = player_weeks['fantasy_points_ppr'].ewm(halflife=3).mean()
    #build standard deviations
    player_weeks['ppr_1ast8_std'] = 
    #build career stats
    player_weeks['ppr_career_mean'] = player_weeks['fantasy_points_ppr'].mean()
    player_weeks['career_games'] = 