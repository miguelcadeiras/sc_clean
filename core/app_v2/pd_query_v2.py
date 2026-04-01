import socket

import numpy as np
import pandas as pd
from sqlalchemy import create_engine


def engine():
    hostname = socket.gethostname()
    ip_addr = socket.gethostbyname(hostname)
    if ip_addr != '151.106.108.129':
        conn = 'mysql+pymysql://webuser:Smartcubik1web@127.0.0.1/inventory'
    else:
        conn = 'mysql+pymysql://smartcubik:Smartcubik1Root!@151.106.108.129/inventory'
    return create_engine(conn)


def pd_df(query, params=None):
    sql_engine = engine()
    with sql_engine.connect() as connection:
        return pd.read_sql(query, connection, params=params)


def virtual_rack(id_inspection):
    query = (
        "select id_Vector, rack, x, codePos, codeUnit, customCode3, visionBar, nivel, picPath "
        "from inventorymaptbl where id_inspection = %s"
    )
    df = pd_df(query, params=[int(id_inspection)])

    if df.empty:
        df['ZERO'] = pd.Series(dtype=bool)
        df['rackLength'] = pd.Series(dtype=float)
        df['vRack'] = pd.Series(dtype='int64')
        return df

    df = df.sort_values('id_Vector').reset_index(drop=True)
    df['ZERO'] = (df['customCode3'] == 'ZERO')

    default_rack_len = df[(df['ZERO']) & (df['x'] > 0.7) & (df['x'] < 3.8)]['x'].median()
    if pd.isna(default_rack_len):
        default_rack_len = 2.7

    subdivisions = 2.0
    virtual_rack_val = 50000
    rack_len = float(default_rack_len)
    mid_rack = False

    rack_lengths = np.empty(len(df), dtype=float)
    vracks = np.empty(len(df), dtype=np.int64)

    for idx in range(len(df) - 1, -1, -1):
        x_val = float(df.at[idx, 'x']) if pd.notna(df.at[idx, 'x']) else 0.0

        if bool(df.at[idx, 'ZERO']):
            mid_rack = True
            virtual_rack_val += 1
            rack_len = x_val if x_val > 0 else rack_len

        if x_val < (rack_len / subdivisions) and mid_rack:
            virtual_rack_val += 1
            mid_rack = False

        rack_lengths[idx] = rack_len

        if rack_len > 1.5 * default_rack_len and pd.notna(df.at[idx, 'rack']):
            vracks[idx] = int(df.at[idx, 'rack'])
        else:
            vracks[idx] = virtual_rack_val

    df['rackLength'] = rack_lengths
    df['vRack'] = vracks
    return df


def running_pos_vr(id_inspection):
    df = virtual_rack(id_inspection)

    df_pos = df[['codePos', 'vRack', 'nivel']].copy()
    df_pos['pos'] = df['codePos'].str[0:10]
    df_pos = df_pos[(df_pos['codePos'].notnull()) & (df_pos['codePos'].str.len() > 0)]
    df_pos = df_pos[['pos', 'vRack']].drop_duplicates()

    df_units = df[['vRack', 'x', 'codeUnit', 'visionBar', 'nivel', 'picPath']].copy()
    df_units = df_units[(df_units['codeUnit'].notnull()) & (df_units['codeUnit'].str.len() > 0)]
    df_units = df_units.drop_duplicates(subset='codeUnit', keep='first')

    return pd.merge(df_pos, df_units, on='vRack', how='right')


def decode_match_levels_sorted(id_inspection):
    df = virtual_rack(id_inspection)

    df_pos = df[['codePos', 'vRack', 'nivel', 'x']].copy()
    df_pos['pos'] = df['codePos'].str[0:10]
    df_pos = df_pos[(df_pos['codePos'].notnull()) & (df_pos['codePos'].str.len() > 0)]
    df_pos = df_pos.sort_values(['vRack', 'nivel'], ascending=(True, False))
    df_pos1 = df_pos[['pos', 'vRack']].drop_duplicates()

    df_units = df[['vRack', 'x', 'codeUnit', 'visionBar', 'nivel', 'picPath']].copy()
    df_units = df_units[(df_units['codeUnit'].notnull()) & (df_units['codeUnit'].str.len() > 0)]
    df_units = df_units.drop_duplicates(subset='codeUnit', keep='first')

    df_pos_units = pd.merge(df_pos1, df_units, on='vRack', how='right')
    df_pos_units = df_pos_units.drop_duplicates(subset='codeUnit', keep='first')

    dfwms = pd_df(
        "select wmsPosition,wmsProduct,wmsDesc,wmsDesc1,wmsdesc2 "
        "from wmspositionmaptbl where id_inspection = %s",
        params=[int(id_inspection)],
    )
    dfwms = dfwms.replace(r'^\s*$', np.nan, regex=True)
    dfwms['wPos'] = dfwms['wmsPosition'].str[4:10]
    dfwms['wmsPos'] = dfwms['wmsPosition'].str[0:10]

    df_products = pd.merge(
        df_pos_units,
        dfwms.dropna(subset=['wmsProduct']),
        how='right',
        left_on='codeUnit',
        right_on='wmsProduct',
    )

    df_no_product = pd.merge(
        dfwms[dfwms['wmsProduct'].isna()],
        df_pos1[['pos']],
        how='left',
        left_on='wmsPos',
        right_on='pos',
    ).drop_duplicates(subset='wmsPosition')

    df_result = pd.concat([df_products, df_no_product], ignore_index=True, sort=False)
    df_result['aPos'] = df_result['pos'].str[4:10]
    df_result['match'] = (df_result['pos'] == df_result['wmsPos'])

    def reason(row):
        if row['match']:
            return ''
        if pd.isna(row['codeUnit']) and pd.notna(row['wmsProduct']):
            return 'missingAGV'
        if pd.notna(row['codeUnit']) and pd.isna(row['wmsProduct']):
            return 'missingWMS'
        try:
            if abs(int(row['wPos']) - int(row['aPos'])) == 2:
                return '2'
        except Exception:
            return 'missMatch'
        return 'missMatch'

    df_result['desc'] = df_result.apply(reason, axis=1)
    df_result['match_original'] = df_result['match']
    df_result['adj2_candidate'] = (
        (df_result['match'] == False)
        & (df_result['desc'] == '2')
        & (df_result['codeUnit'].notna())
        & (df_result['wmsProduct'].notna())
        & (df_result['codeUnit'] == df_result['wmsProduct'])
    )

    # Conservative correction: if same unit is shifted exactly +/-2, mark as corrected match.
    df_result.loc[df_result['adj2_candidate'], 'match'] = True
    df_result.loc[df_result['adj2_candidate'], 'desc'] = 'match_adj2'

    columns = [
        'pos', 'wmsPos', 'vRack', 'x', 'wmsProduct', 'codeUnit', 'visionBar', 'nivel',
        'wmsPosition', 'wmsDesc', 'wmsDesc1', 'wmsdesc2', 'wPos', 'aPos',
        'match', 'match_original', 'adj2_candidate', 'desc', 'picPath'
    ]
    return df_result.reindex(columns=columns)
