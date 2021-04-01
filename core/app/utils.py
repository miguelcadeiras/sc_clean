import pandas as pd


def exportData(array):
    df = pd.DataFrame({'a':array})
    df = df.set_index('a').T
    return df.to_csv('yourData.csv',index=False)

