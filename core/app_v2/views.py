from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import HttpResponse
from django.shortcuts import render

from . import pd_query_v2


@login_required(login_url='/login/')
def all_vr_no_pd_v2(request):
    picpath = []
    levels = []
    last_read = 0

    id_inspection = int(request.GET['id_inspection'])
    matching = request.GET.get('matching', '0')
    qty = max(int(request.GET.get('qty', 500)), 1)
    offset = max(int(request.GET.get('offset', 0)), 0)

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

        dfv = pd_query_v2.pd_df(
            "select product, validation from validationtbl where id_inspection = %s order by id_validation",
            params=[id_inspection],
        )
        dfv = dfv.drop_duplicates(subset='product', keep='last')
        validation_map = dfv.set_index('product')['validation'].to_dict()

        df['verified'] = df['wmsProduct'].map(validation_map).fillna(False)
        df = df[
            ['verified', 'wmsProduct', 'codeUnit', 'nivel', 'pos', 'pos_inferred', 'wmsPosition', 'wmsDesc', 'wmsDesc1', 'wmsdesc2',
             'match', 'desc', 'picPath']
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
                ['waisle', 'wlevel', 'wpos', 'verified', 'wmsProduct', 'codeUnit', 'nivel', 'pos', 'pos_inferred', 'wmsPosition',
                 'wmsDesc', 'wmsDesc1', 'wmsdesc2', 'match', 'desc', 'picPath']
            ].sort_values(['waisle', 'wlevel', 'wpos'], ascending=[True, True, True])
            df = df[df['wmsProduct'] != 'nan']


    total_rows = int(df.shape[0])
    paged_df = df.iloc[offset:offset + qty].copy()
    data = paged_df.values.tolist()

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

    pm2_corrected = int((df['adj2_candidate'] == True).sum()) if 'adj2_candidate' in df.columns else 0

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
        'falsePAlist': paged_df['codeUnit'][(paged_df['match'] == False) & (paged_df['codeUnit'].str.len() > 0)].tolist()[:20]
            if int(matching) > 0 and 'codeUnit' in paged_df.columns and 'match' in paged_df.columns else '',
        'pm2Corrected': pm2_corrected,
        'totalRows': total_rows,
        'offset': offset,
        'qty': qty,
    }

    if matching == '3':
        return render(request, 'allPD_v2/fail_by_v2.html', context)

    return render(request, 'allPD_v2/allPD_v2.html', context)
