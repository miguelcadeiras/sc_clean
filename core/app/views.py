from django.shortcuts import render
import numpy as np
import pandas as pd

# Create your views here.
from django.conf import settings
from django.shortcuts import render
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.template import loader
from django.http import HttpResponse
from django import template
from django.contrib import messages
from django.core.files.storage import FileSystemStorage

import csv, os
from . import querys,utils,pdQuery
from .models import *


@login_required(login_url="/login/")
def index(request):
    # HOME PAGE SHOULD: show warehouses, and select Inspections
    print(request.user)
    clientUser = request.user.profile.client

    id_client, cols = querys.getClientID(clientUser)
    print(id_client)
    data, description = querys.getWarehouses(id_client[0][0])
    # print("data", data)
    # print("description:,", description)
    context = {'data': data,
               'description': description,
               'client': clientUser,

               }

    return render(request, 'warehouses.html', context)


@login_required(login_url="/login/")
def inspections(request):
    # id_inspection = request.GET['id_inspection']
    # levels = querys.getLevels()
    clientUser = request.user.profile.client

    id_client, cols = querys.getClientID(clientUser)
    # print(id_client[0][0])
    data, description = querys.getInspections(request.GET['id_warehouse'])

    context = {'data': data,
               'description': description,
               'client': clientUser,

               # 'levels': levels,
               }

    return render(request, 'inspections.html', context)


@login_required(login_url="/login/")
def all(request):
    picpath = []
    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = "+str(id_inspection))[0][0][0]
    levels = []
    # levels = querys.getLevels(id_inspection)
    if request.GET['matching'] == '0':
        # print('in Get - matching =0')
        data, description = querys.getRunningPositionsCenco(id_inspection,'all','all','all',request.GET['offset'], request.GET['qty'],)
        description = description[0]
        data = data[0]

        # print("CencoDescription",description)
        # print("CencoData",data)

        # data, description = querys.getRunningPositions(request.GET['offset'], request.GET['qty'], id_inspection)
        # description = description[0]
        # data = data[0]
    else:
        data, description = querys.getMatching(id_inspection)
        description = description[1]
        data = data[1]

    query = 'select count(wmsposition) from wmspositionmaptbl where id_inspection=' + str(id_inspection)
    warehouseTotalPositions = querys.mysqlQuery(query)[0][0][0]
    # print( 'warehouseTotalPositions',warehouseTotalPositions)
    query = "select count(wmsProduct) from wmspositionmaptbl where wmsproduct not like '' and id_inspection=" + str(
        id_inspection)
    warehouseUnitCount = querys.mysqlQuery(query)[0][0][0]
    # print('warehouseTotalCount',warehouseUnitCount)
    # en esta query hay que tener encuenta que en cencosud hay etiquetas que son  XX, etiquetas del primer nivel tambien, terminan en 01 y tienen 12 caracteres.
    query = "select count(distinct(codePos)) from inventorymaptbl where codePos not like '' and codePos not like '%XX%' and substring(codePos,11,2) not like '01'  and id_inspection=" + str(
        id_inspection)
    readedPositions = querys.mysqlQuery(query)[0][0][0]
    # print('readedPositions',readedPositions)
    query = "select count(distinct(codeUnit)) from inventorymaptbl where codeUnit not like ''  and id_inspection=" + str(id_inspection)
    readedCount = querys.mysqlQuery(query)[0][0][0]
    # print('readedCount',readedCount)
    # print(data)
    readedRatio = 0

    if int(readedCount) > 0:
        readedRatio = round(readedCount / readedPositions, 2) * 100
        # print('readedRatio',readedRatio)

    warehouseRatio = 0
    if warehouseTotalPositions > 0:
        warehouseRatio = round(warehouseUnitCount / warehouseTotalPositions, 2) * 100
        # print('warehouseRatio',warehouseRatio)

    if request.method == "POST":
        # print("in Post method")
        if 'applyFilter' in request.POST:

            if request.GET['matching'] == '0':
                print("here")
                data, description = querys.getRunningPositionsCenco(id_inspection, request.POST['asile'], request.POST['level'], request.POST['position'],
                                                                    request.GET['offset'], 0)
                description = description[0]
                data = data[0]

            else:
                level = request.POST['level']
                data, description = querys.getMatching(id_inspection, request.POST['asile'], '' if level == 'All' else level)
                description = description[1]
                data = data[1]

        if 'exportData' in request.POST:
            if request.GET['matching'] == '0':

                exportData, desc = querys.getRunningPositionsCenco(id_inspection, 'all', 'all', 'all',0, 0)
                desc = desc[0]
                exportData = exportData[0]
            else:
                # print("in here")
                exportData,desc = querys.getMatching(id_inspection)
                desc = desc[1]
                # print("desc",desc)
                exportData = exportData[1]
                # print("exportData",exportData)


            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename="somefilename.csv"'

            queryUpdateExported = "UPDATE inventorymaptbl set exported = (case codeUnit "

            writer = csv.writer(response)
            writer.writerow(desc)

            for row in exportData:

                writer.writerow(row)
                if request.GET['matching'] == '1':
                    queryUpdateExported += " when '" +str(row[4])+"' then 1 \n"
                    # print("row",row)
                else:
                    queryUpdateExported += " when '" + str(row[4]) + "' then 1 \n"


            messages.success(request, 'Data Exported ')
            queryUpdateExported+= " end) where id_inspection="+str(id_inspection)+";"
            # print(queryUpdateExported)

            querys.execute(queryUpdateExported)

            return response

    context = {'data': data,
               'clientName': request.user.profile.client,
               'id_warehouse':id_warehouse,
               'warehouseName': querys.getWarehouseName(request.GET['id_inspection']),
               'warehouseTotalPositions': warehouseTotalPositions,
               'warehouseTotalCount': warehouseUnitCount,
               'warehouseRatio': warehouseRatio,
               'readedPositions': readedPositions,
               'readedCount': readedCount,
               'readedRatio': readedRatio,
               'inspection': querys.getInspectionData(request.GET['id_inspection']),
               'description': description,
               'picpath': picpath,
               'levels': levels,
               }

    return render(request, 'all.html', context)


@login_required(login_url="/login/")
def allPD(request):
    picpath = []
    levels = []

    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = "+str(id_inspection))[0][0][0]
    if id_inspection == 27:
        levelFactor = {2: 0, 3: 0, 4: 0.2, 5: 0.3}
    else:
        levelFactor = {2: 0, 3: 0, 4: 0, 5:0,6:0,7:0,8:0}
    # levels = querys.getLevels(id_inspection)
    if request.GET['matching'] == '0':
        # print('in Get - matching =0')
        df = pdQuery.fullDeDup(id_inspection,levelFactor)
        df = df[['rack','AGVpos','codeUnit','nivel_y','Ppic']]
        description = ['rack', 'AGVpos', 'codeUnit', 'N','pic']
    else:
        'True to debug. and export file on DecodeMach'
        if 'fullDATA' in request.GET:
            df = pdQuery.decodeMach(id_inspection, levelFactor,False)
        else:
            df = pdQuery.decodeMach(id_inspection, levelFactor,False)

        df = df[['rack','wmsProduct','codeUnit','nivel_y','AGVpos','wmsPosition','wmsDesc','wmsDesc1','wmsDesc2','match','Ppic']]
        description = ['rack','wmsProduct','codeUnit','N','AGVpos','wmsPos','wmsDesc','wmsDesc1','wmsDesc2','c','pic']


    data = df.values.tolist()
    # description = list(df.columns.values)


    query = 'select count(wmsposition) from wmspositionmaptbl where id_inspection=' + str(id_inspection)
    warehouseTotalPositions = querys.mysqlQuery(query)[0][0][0]
    # print( 'warehouseTotalPositions',warehouseTotalPositions)
    query = "select count(wmsProduct) from wmspositionmaptbl where wmsproduct not like '' and id_inspection=" + str(
        id_inspection)
    warehouseUnitCount = querys.mysqlQuery(query)[0][0][0]
    # print('warehouseTotalCount',warehouseUnitCount)
    # en esta query hay que tener encuenta que en cencosud hay etiquetas que son  XX, etiquetas del primer nivel tambien, terminan en 01 y tienen 12 caracteres.
    query = "select count(distinct(codePos)) from inventorymaptbl where codePos not like '' and codePos not like '%XX%' and substring(codePos,11,2) not like '01'  and id_inspection=" + str(
        id_inspection)
    readedPositions = querys.mysqlQuery(query)[0][0][0]
    # print('readedPositions',readedPositions)
    query = "select count(distinct(codeUnit)) from inventorymaptbl where codeUnit not like ''  and id_inspection=" + str(id_inspection)
    readedCount = querys.mysqlQuery(query)[0][0][0]
    # print('readedCount',readedCount)
    # print(data)
    readedRatio = 0


    if int(readedCount) > 0:
        readedRatio = round(readedCount / readedPositions, 2) * 100
        # print('readedRatio',readedRatio)

    warehouseRatio = 0
    if warehouseTotalPositions > 0:
        warehouseRatio = round(warehouseUnitCount / warehouseTotalPositions, 2) * 100
        # print('warehouseRatio',warehouseRatio)

    if request.method == "POST":
        # print("in Post method")
        if 'applyFilter' in request.POST:
            level = request.POST['level']
            asile = request.POST['asile'].zfill(3)
            position = request.POST['position'].zfill(3)
            matching = request.GET['matching']

            for key in request.POST:
                print(key,request.POST[key])

            if level != "All":
                df = df[(df['nivel_y'] == int(level))]
                # data = df.values.tolist()

            if asile != "000":
                print("in asile:",asile)
                if matching == "0":
                    print("in asile 1:", asile)
                    df = df[df["AGVpos"].str[4:7] == asile]
                    # df = df[df["AGVpos"] ]
                else:
                    print("in asile 2:", asile)
                    df = df[df["wmsPosition"].str[4:7] ==asile]

                data = df.values.tolist()

            if position != '000':
                print("in position:",position)

                if matching == "0":
                    print("in position1:", position)
                    print(df["AGVpos"].str[8:10])
                    df = df[df["AGVpos"].str[7:10] == position]
                else:
                    print("in position2:", position)

                    df = df[df["wmsPosition"].str[8:10] == position]

            data = df.values.tolist()

        if 'exportData' in request.POST:
            print("009")

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=exportedData_'+str(id_inspection)+'.csv'
            print("010")

            df.to_csv(path_or_buf=response, sep=',', float_format='%.2f', index=False, decimal=".")

            messages.success(request, 'Data Exported ')

            return response

    print("011")

    context = {'data':data,
               'description':description,
               'clientName': request.user.profile.client,
               'id_warehouse':id_warehouse,
               'warehouseName': querys.getWarehouseName(request.GET['id_inspection']),
               'warehouseTotalPositions': warehouseTotalPositions,
               'warehouseTotalCount': warehouseUnitCount,
               'warehouseRatio': "{:.1f}".format(warehouseRatio),
               'readedPositions': readedPositions,
               'readedCount': readedCount,
               'readedRatio': "{:.1f}".format(readedRatio),
               'readMissMach':"{:.1f}".format((1-(readedCount/warehouseUnitCount))*100) if warehouseUnitCount>0 else "0",
               'inspection': querys.getInspectionData(request.GET['id_inspection']),
               'picpath': picpath,
               'levels': levels,
               }

    return render(request, 'allPD.html', context)


@login_required(login_url="/login/")
def levelPics(request):
    picpath = []
    levels = []

    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = " + str(id_inspection))[0][0][0]
    if id_inspection == 27 or id_inspection == 34:
        levelFactor = {2: 0, 3: 0, 4: 0.2, 5: 0.3}
    else:
        levelFactor = {2: 0, 3: 0, 4: 0, 5:0,6:0,7:0,8:0}

    df = pdQuery.decodeMach(id_inspection, levelFactor, False)
    df = df[
        ['rack', 'wmsProduct', 'codeUnit', 'nivel_y', 'AGVpos', 'wmsPosition', 'wmsDesc', 'wmsDesc1', 'wmsDesc2',
         'match', 'Ppic']]
    description = ['rack', 'wmsProduct', 'codeUnit', 'N', 'AGVpos', 'wmsPos', 'wmsDesc', 'wmsDesc1', 'wmsDesc2',
                   'c', 'pic']

    dfx = df[df["wmsPosition"].notnull()]
    dfa = dfx["wmsPosition"].str[4:7].unique()
    dfl = dfx["wmsPosition"].str[10:12].unique()
    levels = dfl.tolist()
    levels.sort()

    # print(levels)
    gdf = []
    for level in levels:
        # print(level)
        dfy = df.sort_values(by=['wmsPosition'],ascending = True)
        # print("...")
        dfy = dfy[dfy["wmsPosition"].str[10:12] == level]
        dfa = dfy["wmsPosition"].str[4:7].unique()
        cleanDfa = []
        for asile in dfa:
            if len(asile) == 3:
                cleanDfa.append(asile)
        # print("level",level,"..afer",dfa)
        cleanDfa.sort()

        for asile in cleanDfa:
            # para cada pasillo hay que ver cada posición.
            dfLevel = dfy[dfy["wmsPosition"].str[4:7] == asile].sort_values(by=['wmsPosition'],ascending = True)
            dfLevel['wmsPos'] = dfLevel["wmsPosition"].str[4:10]
            dfEven = dfLevel["wmsPos"].fillna(0)
            # dfOdd = dfLevel[int(dfLevel["wmsPos"]) % 2 != 0]

            # print(dfEven)
            # dfLevel["wmsPOS"]
            # print(dfLevel.info())
            gdf.append([level,asile,dfLevel[["wmsPosition",'match','codeUnit','Ppic']].values.tolist()])
            # gdf.append([level,asile,dfEven[["wmsPosition",'match','codeUnit','Ppic']].values.tolist()])
            # gdf.append([level,asile,dfOdd[["wmsPosition",'match','codeUnit','Ppic']].values.tolist()])

            # print("for asile "+ asile +" in data: ",dfLevel["wmsPosition"].str[7:10])

    # print("gdf", gdf)
    data = gdf
    # description = df["wmsPosition"].str[7:10].unique().tolist()
    # print("description",description)
    # print(levels)


    context = {'data': data,
               'description': description,
               'clientName': request.user.profile.client,
               'id_warehouse': id_warehouse,
               'warehouseName': querys.getWarehouseName(request.GET['id_inspection']),
               'inspection': querys.getInspectionData(request.GET['id_inspection']),
               'picpath': picpath,
               'levels': levels,
               }

    return render(request, 'levelPics.html', context)

@login_required(login_url="/login/")
def carrousel(request):
    picpath = []
    levels = []

    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = " + str(id_inspection))[0][0][0]
    if id_inspection == 27 or id_inspection == 34:
        levelFactor = {2: 0, 3: 0, 4: 0.2, 5: 0.3}
    else:
        levelFactor = {2: 0, 3: 0, 4: 0, 5:0,6:0,7:0,8:0}

    df = pdQuery.decodeMach(id_inspection, levelFactor, False)
    print("carrousel df,")
    print(df.columns)
    df = df[
        ['rack', 'wmsProduct', 'codeUnit', 'nivel_y', 'AGVpos', 'wmsPosition', 'wmsDesc', 'wmsDesc1', 'wmsDesc2',
         'match', 'Ppic','upic']]
    description = ['rack', 'wmsProduct', 'codeUnit', 'N', 'AGVpos', 'wmsPos', 'wmsDesc', 'wmsDesc1', 'wmsDesc2',
                   'c', 'pic']

    dfx = df[df["wmsPosition"].notnull()]
    dfa = dfx["wmsPosition"].str[4:7].unique()
    # print("dfa",dfa)
    # pd.set_option("display.max_rows", None, "display.max_columns", None)
    # pd.reset_option('all')
    # print("dfx",dfx["wmsPosition"])
    dfl = dfx["wmsPosition"].str[10:12].unique()
    levels = dfl.tolist()
    # print(levels)
    levels.remove('')
    levels.sort()

    # print(levels)
    gdf = []
    gdfe = []
    gdfo = []
    dfe = {}
    dfo = {}

    #quito los pasillos que por posiciones mal ingresadas no tienen la cantidad de caracteres necesarios.
    # no entiendo por qué es que llegan hasta aca..
    asiles3 = []
    asiles = dfa.tolist()
    # print(asiles)
    asiles.remove('')
    for asile in asiles:
        # print(asile,": len: ",len(asile))
        if len(asile.strip()) == 3:
            asiles3.append(asile)

    asiles3.sort()

    if request.method == "GET":
        getAsile = request.GET['asile']
        if getAsile != '0':
            dfa = [getAsile]
        else:
            dfa = [dfa[-1]]


    for level in levels:
        # print(level)
        dfy = df.sort_values(by=['wmsPosition'],ascending = True)
        # print("...")
        dfy = dfy[dfy["wmsPosition"].str[10:12] == level]
        # dfa = dfy["wmsPosition"].str[4:7].unique()
        # print("level",level,"..afer",dfa)

        for asile in dfa:
            # para cada pasillo hay que ver cada posición.

            dfLevel = dfy[dfy["wmsPosition"].str[4:7] == asile].sort_values(by=['wmsPosition'],ascending = True)
            dfLevel['wmsPos'] = dfLevel["wmsPosition"].str[4:10]
            dfLevel['wmsPos'] = dfLevel["wmsPos"].replace('',np.nan)
            dfLevel['wmsPos'] = dfLevel["wmsPos"].fillna(0)
            # dfEven = dfLevel["wmsPos"].fillna(0)

            dfOdd = dfLevel[dfLevel["wmsPos"].astype('int64') % 2 != 0]
            dfEven = dfLevel[dfLevel["wmsPos"].astype('int64') % 2 == 0]


            gdfe.append([level,asile,dfEven[["wmsPosition",'AGVpos','match','codeUnit','Wpic','upic', 'wmsProduct']].values.tolist()])
            gdfo.append([level,asile,dfOdd[["wmsPosition",'AGVpos','match','codeUnit','Wpic','upic', 'wmsProduct']].values.tolist()])
            dfe[level] = [level,asile,dfEven[["wmsPosition",'AGVpos','match','codeUnit','Wpic','upic', 'wmsProduct']].values.tolist()]
            dfo[level] = [level, asile, dfOdd[["wmsPosition",'AGVpos', 'match', 'codeUnit', 'Wpic','upic', 'wmsProduct']].values.tolist()]
            # print("for asile "+ asile +" in data: ",dfLevel["wmsPosition"].str[7:10])

    # print("gdf", gdf)
    data = gdf
    dataEven = dfe
    dataOdd = dfo



    context = {
            'data': data,
            'asiles': asiles3,
            'levels': levels,
            'dataEven':dataEven,
            'dataOdd': dataOdd,
            'description': description,
            'clientName': request.user.profile.client,
            'id_warehouse': id_warehouse,
            'warehouseName': querys.getWarehouseName(request.GET['id_inspection']),
            'inspection': querys.getInspectionData(request.GET['id_inspection']),
            'picpath': picpath,
            'levels': levels,
            }

    return render(request, 'carrousel.html', context)


@login_required(login_url="/login/")
def level(request):
    id_inspection = request.GET['id_inspection']
    nivel = request.GET['level']
    data, description = querys.unitsByLevel(nivel)
    positions, units = querys.levelOcupation(nivel)
    # print(positions,units)
    ocupation = int(units) / int(positions)
    # print("{:.2f}".format(ocupation*100))
    picpath = []
    levels = querys.getLevels(id_inspection)

    for row in data:
        picpath.insert(0, "assets/smarti/VisionBar0_rack_" + str(row[0]).zfill(8) + "_2021-01-10.bmp")

    # print(len1,description, picpath)
    # print(data)
    context = {'data': data,
               'description': description,
               'picpath': picpath,
               'levels': levels,
               'ocupation_ratio': "{:.2f}".format(ocupation * 100),
               'ocupation': str(units),
               'positions': str(positions)
               }

    return render(request, 'level.html', context)


def testPage(request):
    querys.connect()
    return render(request, 'base.html', {})

@login_required(login_url="/login/")
def importWMS(request):
    id_inspection = request.GET['id_inspection']

    if request.method == "POST":


        if 'Upload' in request.POST.keys():
            # print("myfile", request.POST['myfile'])

            myfile = request.FILES.get('myfile', False)
            print("myfile: ",myfile)
            if myfile != False:
                fs = FileSystemStorage()
                filename = fs.save(myfile.name,myfile)
                print(  "aqui",filename)
                # uploaded_file_url = fs.url(filename)
                # print(uploaded_file_url)
                importBool = querys.importDataBulk(os.path.join(settings.MEDIA_ROOT,filename),id_inspection)
                print("001")
                os.remove(os.path.join(settings.MEDIA_ROOT,filename))
                if importBool:
                    messages.success(request,"Your Data has been Imported correctly")
                else:
                    messages.error(request,"Check your file, we couldn't import it")
            else:
                messages.warning(request,"Please select a file to import")
        else:
            if 'Delete' in request.POST.keys():
                qy = "delete from wmsPositionMapTbl where id_inspection = "+ id_inspection+"; "
                print(qy)
                querys.execute(qy)
                messages.success(request, "WMS Data Deleted")




    data, description = querys.getWMSData(id_inspection)
    query = 'select count(wmsposition) from wmspositionmaptbl where id_inspection=' + str(id_inspection)
    wmsPositions = querys.mysqlQuery(query)[0][0][0]
    wmsPositions = "(" +str(wmsPositions) + ")"

    query = 'select id_warehouse from inspectiontbl where id_inspection=' + str(id_inspection)
    id_warehouse = querys.mysqlQuery(query)[0][0][0]

    context = {"data": data[0],
               "description": description[0],
               "wmsPositions":wmsPositions,
               "id_warehouse":id_warehouse,
               }
    return render(request, 'importWMS.html', context)

# @login_required(login_url="/login/")
# def pages(request):
#     context = {}
#     # All resource paths end in .html.
#     # Pick out the html file name from the url. And load that template.
#     try:
#
#         load_template = request.path.split('/')[-1]
#         context['segment'] = load_template
#
#         html_template = loader.get_template(load_template)
#         return HttpResponse(html_template.render(context, request))
#
#     except template.TemplateDoesNotExist:
#
#         html_template = loader.get_template('page-404.html')
#         return HttpResponse(html_template.render(context, request))
#
#     except:
#
#         html_template = loader.get_template('page-500.html')
#         return HttpResponse(html_template.render(context, request))
