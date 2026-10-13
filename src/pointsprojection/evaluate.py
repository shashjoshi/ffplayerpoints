#imports
import pandas as pd
import numpy as np
from pointsprojection import features, models
import sklearn.metrics as sklm



#Get training splits and return a list of (training row, validation row) pairs
#6 folds, with validation row Y having training rows 2016 to Y-1
#2025/26 held for out-of-sample testing later
def seasonsplits (feat_df):
    val_seasons = [2017, 2018, 2019, 2020, 2021, 2022, 2023, 2024]
    retlist = [[],[]]
    for i in val_seasons:
        training = feat_df[feat_df['season'] < i].reset_index(drop = True)
        validation = feat_df[feat_df['season'] == i].reset_index(drop=True)
        retlist[0].append(training)
        retlist[1].append(validation)
    return retlist


def computemetrics (df, preds):
    #define target
    target = features.featurereg['target'][0]
    #Assign predictions to the df ans strip pandas indexing
    df = df.assign(pred = np.asarray(preds))
    #Calculate Mean Absolute Error 
    mae = sklm.mean_absolute_error(df['pred'], df[target])
    #Calculate Root Mean Squared Error
    rmse = sklm.root_mean_squared_error(df['pred'], df[target])
    #Calculate Directional Bias
    bias = (df['pred']-df[target]).mean()
    #Calculate MAE per position group
    maeperpos = df.groupby('position').apply(
        lambda x : sklm.mean_absolute_error(x['pred'], x[target])
    )
    #Calculate Spearman correlation between actual and predicted values
    corr = df.groupby(['season', 'week', 'position']).apply(
        lambda x: x[target].corr(x['pred'], method = 'spearman')
    ).mean()
    #Return Dictionary
    retdict = {
        'mae': mae,
        'rmse': rmse,
        'bias': bias,
        'maeperpos': maeperpos,
        'corr': corr
    }
    return retdict

#Marks the realistic starters for each season, week, position
#Ex. top 36 QBs, Top 50 RBs, Top 50 WRs
realistic_cutoffs = {'QB':26, 'RB':50, 'WR':50, 'TE':36}
#Ranked by pre-game ppr_ewm
def startablemask(df):
    rank = df.groupby(['season', 'week', 'position'])['ppr_ewm'].rank(method='first',ascending=False)
    df['startable'] = rank <= df['position'].map(realistic_cutoffs)
    return df


def crossvalidate(model_fn, features_df, feature_cols, target, val_seasons):


def comparemodels(results):


def finaltest(model_fn, features_df, feature_cols, target, test_seasons):


