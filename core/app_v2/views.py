from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from . import pd_query_v2


def false_pa_window_map(df, window_size=3):
    if 'codeUnit' not in df.columns or 'match' not in df.columns:
        return {}

    code_units = df.loc[
        (df['match'] == False) & (df['codeUnit'].str.len() > 0),
        'codeUnit',
    ].astype(str).tolist()

    result = {}
    for index, code_unit in enumerate(code_units):
        start = max(index - window_size, 0)
        end = min(index + window_size + 1, len(code_units))
        result[code_unit] = str(code_units[start:end])
    return result


def pm2_diagnostics(id_inspection, v2_df):
    pm2_mask = v2_df['desc'] == '2' if 'desc' in v2_df.columns else False
    diagnostics = {
        'legacyMismatchCount': 'n/a',
        'v2MismatchCount': int((v2_df['match'] == False).sum()) if 'match' in v2_df.columns else 0,
        'legacyPm2Count': 'n/a',
        'v2Pm2Count': int(pm2_mask.sum()) if hasattr(pm2_mask, 'sum') else 0,
        'pm2ResolvedByV2': 'n/a',
        'pm2WmsAi': int((v2_df['VerifiedAI'] == 'wmsAI').sum()) if 'VerifiedAI' in v2_df.columns else 0,
        'pm2AgvAi': int((pm2_mask & (v2_df['VerifiedAI'] == 'agvAI')).sum())
            if hasattr(pm2_mask, 'sum') and 'VerifiedAI' in v2_df.columns else 0,
        'pm2RemainingToCheck': int((pm2_mask & ~v2_df['VerifiedAI'].isin(['wmsAI', 'agvAI'])).sum())
            if hasattr(pm2_mask, 'sum') and 'VerifiedAI' in v2_df.columns else 0,
        'pm2DiagnosticsError': '',
    }

    try:
        legacy_summary = pd_query_v2.legacy_matching_summary(id_inspection)
        diagnostics['legacyMismatchCount'] = legacy_summary['legacyMismatchCount']
        diagnostics['legacyPm2Count'] = legacy_summary['legacyPm2Count']
        if isinstance(diagnostics['legacyPm2Count'], int):
            diagnostics['pm2ResolvedByV2'] = diagnostics['legacyPm2Count'] - diagnostics['v2Pm2Count']
    except Exception as exc:
        diagnostics['pm2DiagnosticsError'] = str(exc)

    return diagnostics


@login_required(login_url='/login/')
def all_vr_no_pd_v2(request):
    picpath = []
    levels = []
    last_read = 0

    id_inspection = int(request.GET['id_inspection'])
    matching = request.GET.get('matching', '0')
    qty_param = request.GET.get('qty', '500')
    show_all_rows = str(qty_param).lower() == 'all'
    qty = None if show_all_rows else max(int(qty_param), 1)
    offset = 0 if show_all_rows else max(int(request.GET.get('offset', 0)), 0)

    id_warehouse_df = pd_query_v2.pd_df(
        "select id_warehouse from inspectiontbl where id_inspection = %s",
        params=[id_inspection],
    )
    id_warehouse = id_warehouse_df.iloc[0]['id_warehouse'] if not id_warehouse_df.empty else 0

    if matching == '0':
        df = pd_query_v2.running_pos_vr(id_inspection)
        df = df[['vRack', 'pos', 'codeUnit', 'nivel', 'picPath']]
    else:
        df = pd_query_v2.decode_match_levels_sorted(id_inspection).fillna('')
        diagnostics = pm2_diagnostics(id_inspection, df)

        dfv = pd_query_v2.pd_df(
            "select product, validation from validationtbl where id_inspection = %s order by id_validation",
            params=[id_inspection],
        )
        dfv = dfv.drop_duplicates(subset='product', keep='last')
        validation_map = dfv.set_index('product')['validation'].to_dict()

        df['verified'] = df['wmsProduct'].map(validation_map).fillna(False)
        df = df[
            ['verified', 'wmsProduct', 'codeUnit', 'nivel', 'pos', 'wmsPosition', 'match', 'desc',
             'matchAI', 'VerifiedAI', 'aiReason', 'wmsDesc', 'wmsDesc1', 'wmsdesc2', 'picPath']
        ]
        df = df[df['wmsProduct'] != 'nan']

        if matching in ('2', '3'):
            df = df[(df['match'] == False) & (df['wmsProduct'] != '')]

        if matching == '3':
            try:
                df['waisle'] = df['wmsPosition'].str[4:7]
                df['wlevel'] = df['wmsPosition'].str[10:12]
                df['wpos'] = df['wmsPosition'].str[7:10]
            except Exception:
                messages.warning(request, 'There are values on Aisle, Level or Pos that brings conflicts.')

            df = df[
                ['waisle', 'wlevel', 'wpos', 'verified', 'wmsProduct', 'codeUnit', 'nivel', 'pos',
                 'wmsPosition', 'match', 'desc', 'matchAI', 'VerifiedAI',
                 'aiReason', 'wmsDesc', 'wmsDesc1', 'wmsdesc2', 'picPath']
            ].sort_values(['waisle', 'wlevel', 'wpos'], ascending=[True, True, True])
            df = df[df['wmsProduct'] != 'nan']
    if matching == '0':
        diagnostics = {
            'legacyMismatchCount': 'n/a',
            'v2MismatchCount': 'n/a',
            'legacyPm2Count': 'n/a',
            'v2Pm2Count': 'n/a',
            'pm2ResolvedByV2': 'n/a',
            'pm2WmsAi': 'n/a',
            'pm2AgvAi': 'n/a',
            'pm2RemainingToCheck': 'n/a',
            'pm2DiagnosticsError': '',
        }


    total_rows = int(df.shape[0])
    false_pa_list_by_unit = false_pa_window_map(df) if int(matching) > 0 else {}
    if show_all_rows:
        paged_df = df.copy()
        page_qty = total_rows if total_rows > 0 else 1
    else:
        paged_df = df.iloc[offset:offset + qty].copy()
        page_qty = qty
    data = paged_df.values.tolist()
    prev_offset = max(offset - page_qty, 0)
    next_offset = offset + page_qty
    prev_params = request.GET.copy()
    next_params = request.GET.copy()
    qty_500_params = request.GET.copy()
    qty_1000_params = request.GET.copy()
    qty_all_params = request.GET.copy()
    prev_params['offset'] = str(prev_offset)
    prev_params['qty'] = str(page_qty)
    next_params['offset'] = str(next_offset)
    next_params['qty'] = str(page_qty)
    qty_500_params['offset'] = '0'
    qty_500_params['qty'] = '500'
    qty_1000_params['offset'] = '0'
    qty_1000_params['qty'] = '1000'
    qty_all_params['offset'] = '0'
    qty_all_params['qty'] = 'all'

    metrics_df = pd_query_v2.pd_df(
        """
        select
            (select count(wmsposition) from wmspositionmaptbl where id_inspection = %s) as warehouse_total_positions,
            (select count(wmsProduct) from wmspositionmaptbl where wmsproduct not like '' and id_inspection = %s) as warehouse_unit_count,
            (select count(distinct(codePos)) from inventorymaptbl
                where codePos not like ''
                  and codePos not like '%%XX%%'
                  and substring(codePos,11,2) not like '01'
                  and id_inspection = %s) as readed_positions,
            (select count(distinct(codeUnit)) from inventorymaptbl
                where codeUnit not like ''
                  and id_inspection = %s) as readed_count
        """,
        params=[id_inspection, id_inspection, id_inspection, id_inspection],
    )

    warehouse_total_positions = int(metrics_df.iloc[0]['warehouse_total_positions']) if not metrics_df.empty else 0
    warehouse_unit_count = int(metrics_df.iloc[0]['warehouse_unit_count']) if not metrics_df.empty else 0
    readed_positions = int(metrics_df.iloc[0]['readed_positions']) if not metrics_df.empty else 0
    readed_count = int(metrics_df.iloc[0]['readed_count']) if not metrics_df.empty else 0

    readed_ratio = round(readed_count / readed_positions, 2) * 100 if readed_count > 0 and readed_positions > 0 else 0
    warehouse_ratio = round(warehouse_unit_count / warehouse_total_positions, 2) * 100 if warehouse_total_positions > 0 else 0

    if request.method == 'POST' and 'exportData' in request.POST:
        response = HttpResponse(content_type='text/csv')
        response['Content-Disposition'] = f'attachment; filename=exportedData_{id_inspection}.csv'
        df.to_csv(path_or_buf=response, sep=',', float_format='%.2f', index=False, decimal='.')
        messages.success(request, 'Data Exported')
        return response

    inspection_df = pd_query_v2.pd_df(
        "select description, inspectionDate from inspectiontbl where id_inspection = %s",
        params=[id_inspection],
    )
    inspection_data = inspection_df.values.tolist()[0] if not inspection_df.empty else ['', '']

    warehouse_name_df = pd_query_v2.pd_df(
        """
        select warehousestbl.name,address,city,country
        from warehousestbl
        inner join inspectiontbl on inspectiontbl.id_warehouse = warehousestbl.id_warehouse
        where id_inspection = %s
        """,
        params=[id_inspection],
    )
    warehouse_name = warehouse_name_df.values.tolist()

    if not df.empty:
        last_read_df = pd_query_v2.pd_df(
            """
            select substring(codePos,5,6) as lastread
            from inventorymaptbl
            where id_inspection = %s and codePos not like ''
            order by id_Vector desc
            limit 1
            """,
            params=[id_inspection],
        )
        if not last_read_df.empty and isinstance(last_read_df.iloc[0]['lastread'], str):
            lr = last_read_df.iloc[0]['lastread']
            last_read = f"Aisle:{lr[0:3]} Pos:{lr[3:6]}"

    context = {
        'data': data,
        'description': df.columns.tolist(),
        'clientName': request.user.profile.client,
        'id_warehouse': id_warehouse,
        'warehouseName': warehouse_name,
        'warehouseTotalPositions': warehouse_total_positions,
        'warehouseTotalCount': warehouse_unit_count,
        'warehouseRatio': f"{warehouse_ratio:.1f}",
        'readedPositions': readed_positions,
        'readedCount': readed_count,
        'readedRatio': f"{readed_ratio:.1f}",
        'readMissMach': f"{(1 - (readed_count / warehouse_unit_count)) * 100:.1f}" if warehouse_unit_count > 0 else '0',
        'inspection': inspection_data,
        'picpath': picpath,
        'levels': levels,
        'lastRead': last_read,
        'falsePAlist': '',
        'falsePAListByUnit': false_pa_list_by_unit,
        'legacyMismatchCount': diagnostics['legacyMismatchCount'],
        'v2MismatchCount': diagnostics['v2MismatchCount'],
        'legacyPm2Count': diagnostics['legacyPm2Count'],
        'v2Pm2Count': diagnostics['v2Pm2Count'],
        'pm2ResolvedByV2': diagnostics['pm2ResolvedByV2'],
        'pm2WmsAi': diagnostics['pm2WmsAi'],
        'pm2AgvAi': diagnostics['pm2AgvAi'],
        'pm2RemainingToCheck': diagnostics['pm2RemainingToCheck'],
        'pm2DiagnosticsError': diagnostics['pm2DiagnosticsError'],
        'totalRows': total_rows,
        'offset': offset,
        'qty': qty,
        'pageStart': offset + 1 if total_rows > 0 else 0,
        'pageEnd': total_rows if show_all_rows else min(offset + page_qty, total_rows),
        'hasPrevPage': not show_all_rows and offset > 0,
        'hasNextPage': not show_all_rows and next_offset < total_rows,
        'prevPageUrl': f"?{prev_params.urlencode()}",
        'nextPageUrl': f"?{next_params.urlencode()}",
        'qty500Url': f"?{qty_500_params.urlencode()}",
        'qty1000Url': f"?{qty_1000_params.urlencode()}",
        'qtyAllUrl': f"?{qty_all_params.urlencode()}",
        'showAllRows': show_all_rows,
    }

    if matching == '3':
        return render(request, 'allPD_v2/fail_by_v2.html', context)

    return render(request, 'allPD_v2/allPD_v2.html', context)
