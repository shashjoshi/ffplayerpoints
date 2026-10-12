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


