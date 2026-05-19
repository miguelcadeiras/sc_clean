import os
import socket

import numpy as np
import pandas as pd
from sqlalchemy import create_engine


MATCHING_AI_RULES_DOC = 'docs/v2_matching_ai_rules.md'
PALLET_WINDOW_M = 1.2
RESET_DROP_M = 0.8
RESET_MIN_PREV_X = 1.8
RESET_MAX_CURRENT_X = 0.8
VIRTUAL_RACK_CACHE_TABLE = 'v2_virtual_rack_cache'
VIRTUAL_RACK_CACHE_META_TABLE = 'v2_virtual_rack_cache_meta'
LEGACY_SUMMARY_CACHE_TABLE = 'v2_legacy_matching_summary_cache'


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


def execute_sql(query, params=None, many=False):
    sql_engine = engine()
    raw_connection = sql_engine.raw_connection()
    try:
        cursor = raw_connection.cursor()
        if many:
            cursor.executemany(query, params or [])
        else:
            cursor.execute(query, params or ())
        raw_connection.commit()
    finally:
        raw_connection.close()


def cache_enabled():
    return os.environ.get('SC_V2_VIRTUAL_RACK_CACHE', '1') != '0'


def ensure_virtual_rack_cache_tables():
    execute_sql(
        f"""
        create table if not exists {VIRTUAL_RACK_CACHE_TABLE} (
            id_inspection int not null,
            id_Vector int not null,
            ZERO tinyint(1) not null,
            rackLength double null,
            vRack int not null,
            cached_at timestamp not null default current_timestamp,
            primary key (id_inspection, id_Vector),
            index idx_v2_vrack_cache_inspection (id_inspection)
        )
        """
    )
    execute_sql(
        f"""
        create table if not exists {VIRTUAL_RACK_CACHE_META_TABLE} (
            id_inspection int not null primary key,
            source_row_count int not null,
            source_max_vector int not null,
            cached_at timestamp not null default current_timestamp on update current_timestamp
        )
        """
    )


def ensure_legacy_summary_cache_table():
    execute_sql(
        f"""
        create table if not exists {LEGACY_SUMMARY_CACHE_TABLE} (
            id_inspection int not null primary key,
            source_row_count int not null,
            source_max_vector int not null,
            legacy_mismatch_count int not null,
            legacy_pm2_count int not null,
            cached_at timestamp not null default current_timestamp on update current_timestamp
        )
        """
    )


def inventory_signature(id_inspection):
    signature = pd_df(
        """
        select count(*) as row_count, coalesce(max(id_Vector), 0) as max_vector
        from inventorymaptbl
        where id_inspection = %s
        """,
        params=[int(id_inspection)],
    )
    if signature.empty:
        return 0, 0
    return int(signature.iloc[0]['row_count']), int(signature.iloc[0]['max_vector'])


def cached_virtual_rack(id_inspection, signature):
    ensure_virtual_rack_cache_tables()
    row_count, max_vector = signature
    meta = pd_df(
        f"""
        select source_row_count, source_max_vector
        from {VIRTUAL_RACK_CACHE_META_TABLE}
        where id_inspection = %s
        """,
        params=[int(id_inspection)],
    )
    if meta.empty:
        return None
    if int(meta.iloc[0]['source_row_count']) != row_count:
        return None
    if int(meta.iloc[0]['source_max_vector']) != max_vector:
        return None

    cached = pd_df(
        f"""
        select
            i.id_Vector, i.rack, i.x, i.codePos, i.codeUnit, i.customCode3,
            i.visionBar, i.nivel, i.picPath,
            c.ZERO, c.rackLength, c.vRack
        from inventorymaptbl i
        inner join {VIRTUAL_RACK_CACHE_TABLE} c
            on c.id_inspection = i.id_inspection
            and c.id_Vector = i.id_Vector
        where i.id_inspection = %s
        order by i.id_Vector
        """,
        params=[int(id_inspection)],
    )
    if len(cached) != row_count:
        return None
    cached['ZERO'] = cached['ZERO'].astype(bool)
    return cached


def persist_virtual_rack_cache(id_inspection, df, signature):
    ensure_virtual_rack_cache_tables()
    row_count, max_vector = signature

    execute_sql(
        f"delete from {VIRTUAL_RACK_CACHE_TABLE} where id_inspection = %s",
        params=(int(id_inspection),),
    )
    rows = [
        (
            int(id_inspection),
            int(row.id_Vector),
            1 if bool(row.ZERO) else 0,
            None if pd.isna(row.rackLength) else float(row.rackLength),
            int(row.vRack),
        )
        for row in df[['id_Vector', 'ZERO', 'rackLength', 'vRack']].itertuples(index=False)
    ]
    if rows:
        execute_sql(
            f"""
            insert into {VIRTUAL_RACK_CACHE_TABLE}
                (id_inspection, id_Vector, ZERO, rackLength, vRack)
            values (%s, %s, %s, %s, %s)
            """,
            params=rows,
            many=True,
        )

    execute_sql(
        f"""
        insert into {VIRTUAL_RACK_CACHE_META_TABLE}
            (id_inspection, source_row_count, source_max_vector)
        values (%s, %s, %s)
        on duplicate key update
            source_row_count = values(source_row_count),
            source_max_vector = values(source_max_vector),
            cached_at = current_timestamp
        """,
        params=(int(id_inspection), row_count, max_vector),
    )


def legacy_matching_summary(id_inspection, refresh_cache=False):
    signature = inventory_signature(id_inspection)
    row_count, max_vector = signature

    if cache_enabled() and not refresh_cache:
        ensure_legacy_summary_cache_table()
        cached = pd_df(
            f"""
            select legacy_mismatch_count, legacy_pm2_count, source_row_count, source_max_vector
            from {LEGACY_SUMMARY_CACHE_TABLE}
            where id_inspection = %s
            """,
            params=[int(id_inspection)],
        )
        if not cached.empty:
            if int(cached.iloc[0]['source_row_count']) == row_count:
                if int(cached.iloc[0]['source_max_vector']) == max_vector:
                    return {
                        'legacyMismatchCount': int(cached.iloc[0]['legacy_mismatch_count']),
                        'legacyPm2Count': int(cached.iloc[0]['legacy_pm2_count']),
                    }

    from app import pdQuery as legacy_pd_query

    legacy_df = legacy_pd_query.decodeMachVR_noPD_levels_sorted(id_inspection).fillna('')
    summary = {
        'legacyMismatchCount': int((legacy_df['match'] == False).sum()) if 'match' in legacy_df.columns else 0,
        'legacyPm2Count': int((legacy_df['desc'] == '2').sum()) if 'desc' in legacy_df.columns else 0,
    }

    if cache_enabled():
        ensure_legacy_summary_cache_table()
        execute_sql(
            f"""
            insert into {LEGACY_SUMMARY_CACHE_TABLE}
                (id_inspection, source_row_count, source_max_vector, legacy_mismatch_count, legacy_pm2_count)
            values (%s, %s, %s, %s, %s)
            on duplicate key update
                source_row_count = values(source_row_count),
                source_max_vector = values(source_max_vector),
                legacy_mismatch_count = values(legacy_mismatch_count),
                legacy_pm2_count = values(legacy_pm2_count),
                cached_at = current_timestamp
            """,
            params=(
                int(id_inspection),
                row_count,
                max_vector,
                summary['legacyMismatchCount'],
                summary['legacyPm2Count'],
            ),
        )

    return summary


def raw_inventory(id_inspection):
    query = (
        "select id_Vector, rack, x, codePos, codeUnit, customCode3, visionBar, nivel, picPath "
        "from inventorymaptbl where id_inspection = %s"
    )
    return pd_df(query, params=[int(id_inspection)])


def compute_virtual_rack(df):
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


def virtual_rack(id_inspection, refresh_cache=False):
    signature = inventory_signature(id_inspection)
    if cache_enabled() and not refresh_cache:
        cached = cached_virtual_rack(id_inspection, signature)
        if cached is not None:
            return cached

    df = compute_virtual_rack(raw_inventory(id_inspection))
    if cache_enabled():
        persist_virtual_rack_cache(id_inspection, df, signature)
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


def position_base(code):
    if not isinstance(code, str) or len(code) < 10:
        return ''
    return code[:10]


def position_level(code):
    if not isinstance(code, str) or len(code) < 12:
        return ''
    level = code[10:12]
    return '' if level == 'XX' else level


def normalized_level(value):
    if pd.isna(value):
        return ''
    try:
        return f'{int(float(value)):02d}'
    except Exception:
        return str(value).zfill(2)


def parsed_position_base(pos_base):
    if not isinstance(pos_base, str) or len(pos_base) < 10:
        return None, None
    pos_num = pos_base[7:10]
    if not pos_num.isdigit():
        return None, None
    return pos_base[:7], int(pos_num)


def format_position_base(prefix, pos_num):
    if not prefix or pos_num < 0 or pos_num > 999:
        return ''
    return f'{prefix}{pos_num:03d}'


def add_encoder_windows(
    inventory_df,
    pallet_window_m=PALLET_WINDOW_M,
    reset_drop_m=RESET_DROP_M,
    reset_min_prev_x=RESET_MIN_PREV_X,
    reset_max_current_x=RESET_MAX_CURRENT_X,
):
    df = inventory_df.sort_values('id_Vector').copy()
    df['prev_x'] = df['x'].shift(1)
    df['x_reset'] = (
        df['x'].notna()
        & df['prev_x'].notna()
        & (df['prev_x'] > reset_min_prev_x)
        & (df['x'] < reset_max_current_x)
        & (df['x'] < df['prev_x'] - reset_drop_m)
    )
    df['encoder_segment'] = df['x_reset'].cumsum()
    df['pallet_window'] = np.floor(df['x'].fillna(-1) / pallet_window_m).astype(int)
    return df


def physical_position_candidates(inventory_df):
    # Keep this evidence threshold aligned with docs/v2_matching_ai_rules.md.
    code_pos = inventory_df[inventory_df['codePos'].notna()].copy()
    code_pos = code_pos[code_pos['codePos'].str.len() >= 10]
    if code_pos.empty:
        return {}

    code_pos['pos_base'] = code_pos['codePos'].apply(position_base)
    candidates = {}
    grouped = code_pos.groupby(['encoder_segment', 'pallet_window'])

    for key, group in grouped:
        counts = group['pos_base'].value_counts()
        winner = counts.index[0]
        winner_count = int(counts.iloc[0])
        runner_up_count = int(counts.iloc[1]) if len(counts) > 1 else 0

        if winner_count < 2:
            continue
        if runner_up_count > 0 and winner_count < runner_up_count * 2:
            continue

        candidates[key] = winner

    return candidates


def rack_position_candidates(inventory_df):
    code_pos = inventory_df[
        inventory_df['rack'].notna()
        & inventory_df['codePos'].notna()
        & (inventory_df['codePos'].str.len() >= 10)
    ].copy()
    if code_pos.empty:
        return {}

    code_pos['pos_base'] = code_pos['codePos'].apply(position_base)
    candidates = {}
    grouped = code_pos.groupby('rack')

    for rack, group in grouped:
        counts = group['pos_base'].value_counts()
        winner = counts.index[0]
        winner_count = int(counts.iloc[0])
        runner_up_count = int(counts.iloc[1]) if len(counts) > 1 else 0

        if runner_up_count > 0 and winner_count < runner_up_count * 2:
            continue
        prefix, pos_num = parsed_position_base(winner)
        if prefix is None:
            continue

        candidates[int(rack)] = winner

    return candidates


def sequence_position_candidates(inventory_df, max_gap_racks=4):
    rack_positions = rack_position_candidates(inventory_df)
    unit_racks = inventory_df[
        inventory_df['rack'].notna()
        & inventory_df['codeUnit'].notna()
        & (inventory_df['codeUnit'].str.len() > 0)
    ]['rack'].drop_duplicates()

    candidates = {}
    known_racks = sorted(rack_positions)

    for rack_value in unit_racks:
        rack = int(rack_value)
        if rack in rack_positions:
            continue

        prev_rack = next((known for known in reversed(known_racks) if known < rack), None)
        next_rack = next((known for known in known_racks if known > rack), None)
        if prev_rack is None or next_rack is None:
            continue
        if (rack - prev_rack) > max_gap_racks or (next_rack - rack) > max_gap_racks:
            continue

        prev_prefix, prev_pos = parsed_position_base(rack_positions[prev_rack])
        next_prefix, next_pos = parsed_position_base(rack_positions[next_rack])
        if prev_prefix is None or prev_prefix != next_prefix:
            continue

        rack_gap = next_rack - prev_rack
        pos_gap = next_pos - prev_pos
        if abs(pos_gap) != 2 * rack_gap:
            continue

        step = pos_gap // rack_gap
        inferred_pos = prev_pos + step * (rack - prev_rack)
        candidates[rack] = format_position_base(prev_prefix, inferred_pos)

    return candidates


def decode_match_levels_sorted(id_inspection):
    df = add_encoder_windows(virtual_rack(id_inspection))
    rack_candidates = rack_position_candidates(df)
    physical_candidates = physical_position_candidates(df)
    sequence_candidates = sequence_position_candidates(df)

    df_pos = df[['codePos', 'vRack', 'nivel', 'x']].copy()
    df_pos['pos'] = df['codePos'].str[0:10]
    df_pos = df_pos[(df_pos['codePos'].notnull()) & (df_pos['codePos'].str.len() > 0)]
    df_pos = df_pos.sort_values(['vRack', 'nivel'], ascending=(True, False))
    df_pos1 = df_pos[['pos', 'vRack']].drop_duplicates()

    df_units = df[
        ['id_Vector', 'rack', 'vRack', 'encoder_segment', 'pallet_window', 'x', 'codeUnit', 'visionBar', 'nivel', 'picPath']
    ].copy()
    df_units = df_units.rename(columns={'id_Vector': 'unit_id_Vector'})
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
    df_result['pos_legacy'] = df_result['pos']
    df_result['pos_rack'] = ''
    df_result['pos_physical'] = ''
    df_result['pos_sequence'] = ''
    unit_rows = df_result['encoder_segment'].notna() & df_result['pallet_window'].notna()
    for idx, row in df_result[unit_rows].iterrows():
        key = (int(row['encoder_segment']), int(row['pallet_window']))
        df_result.at[idx, 'pos_physical'] = physical_candidates.get(key, '')
    rack_rows = df_result['rack'].notna()
    for idx, row in df_result[rack_rows].iterrows():
        df_result.at[idx, 'pos_rack'] = rack_candidates.get(int(row['rack']), '')
        df_result.at[idx, 'pos_sequence'] = sequence_candidates.get(int(row['rack']), '')
    df_result['posSource'] = 'legacy'
    has_physical_pos = df_result['pos_physical'] != ''
    physical_supports_wms = has_physical_pos & (df_result['pos_physical'] == df_result['wmsPos'])
    df_result.loc[physical_supports_wms, 'pos'] = df_result.loc[physical_supports_wms, 'pos_physical']
    df_result.loc[has_physical_pos, 'posSource'] = 'physical'
    sequence_supports_wms = (df_result['pos_sequence'] != '') & (df_result['pos_sequence'] == df_result['wmsPos'])
    sequence_changed_pos = sequence_supports_wms & (df_result['pos_sequence'] != df_result['pos_legacy'])
    df_result.loc[sequence_changed_pos, 'pos'] = df_result.loc[sequence_changed_pos, 'pos_sequence']
    df_result.loc[sequence_changed_pos, 'posSource'] = 'sequence'
    rack_supports_wms = (df_result['pos_rack'] != '') & (df_result['pos_rack'] == df_result['wmsPos'])
    rack_changed_pos = rack_supports_wms & (df_result['pos_rack'] != df_result['pos_legacy'])
    df_result.loc[rack_changed_pos, 'pos'] = df_result.loc[rack_changed_pos, 'pos_rack']
    df_result.loc[rack_changed_pos, 'posSource'] = 'rack'
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
    # NOTE: +/-2 is only a diagnostic label. We must not mark it as corrected
    # just because the same pallet appears two positions away.
    df_result['adj2_candidate'] = False
    df_result['match_corrected'] = df_result['match']
    df_result['pos_inferred'] = ''

    df_result['matchAI'] = df_result['match']
    df_result['VerifiedAI'] = False
    df_result['aiReason'] = ''
    physical_rows = df_result['posSource'] == 'physical'
    sequence_rows = df_result['posSource'] == 'sequence'
    rack_rows = df_result['posSource'] == 'rack'
    physical_changed_pos = physical_rows & (df_result['pos_physical'] != df_result['pos_legacy'])
    df_result.loc[physical_supports_wms & physical_changed_pos & (df_result['match'] == True), 'VerifiedAI'] = 'wmsAI'
    df_result.loc[sequence_rows & (df_result['match'] == True), 'VerifiedAI'] = 'wmsAI'
    df_result.loc[rack_rows & (df_result['match'] == True), 'VerifiedAI'] = 'wmsAI'
    df_result.loc[
        physical_rows
        & (df_result['match'] == False)
        & (df_result['pos_physical'] == df_result['pos_legacy'])
        & (df_result['pos_legacy'] != df_result['wmsPos']),
        'VerifiedAI'
    ] = 'agvAI'
    df_result.loc[df_result['VerifiedAI'] == 'wmsAI', 'aiReason'] = 'WMS wins'
    df_result.loc[df_result['VerifiedAI'] == 'agvAI', 'aiReason'] = 'AGV wins'

    columns = [
        'pos', 'wmsPos', 'vRack', 'unit_id_Vector', 'x', 'wmsProduct', 'codeUnit', 'visionBar', 'nivel',
        'wmsPosition', 'wmsDesc', 'wmsDesc1', 'wmsdesc2', 'wPos', 'aPos',
        'match', 'match_original', 'adj2_candidate', 'match_corrected', 'pos_inferred', 'matchAI',
        'VerifiedAI', 'aiReason', 'rack', 'pos_legacy', 'pos_rack', 'pos_physical', 'pos_sequence',
        'posSource', 'desc', 'picPath'
    ]
    return df_result.reindex(columns=columns)
