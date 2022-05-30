import json
import time
from django.shortcuts import render
import numpy as np
import pandas as pd
from django.contrib.auth.models import User, Group
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
from . import querys,utils,pdQuery,flags
from .models import *


@login_required(login_url="/login/")
def index(request):
    # HOME PAGE SHOULD: show warehouses, and select Inspections
    # print(request.user)
    clientUser = request.user.profile.client

    id_client, cols = querys.getClientID(clientUser)
    # print(id_client)
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


    lastRead = "NULL"
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
               'lastRead':lastRead
               }

    return render(request, 'all.html', context)


@login_required(login_url="/login/")
def allPD(request):
    # dvr =pdQuery.virtualRack(98)
    # print(dvr)
    # dfpm10=pdQuery.plusminus10Pos(98,"UBG1002002")


    picpath = []
    levels = []
    lastRead =0
    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = "+str(id_inspection))[0][0][0]
    # if id_inspection == 27:
    #     levelFactor = {1:0,2: 0, 3: 0, 4: 0.2, 5: 0.3}
    # else:
    #     levelFactor = {1:0,2: 0, 3: 0, 4: 0, 5:0,6:0,7:0,8:0}
    # # levels = querys.getLevels(id_inspection)
    if request.GET['matching'] == '0':
        # print('in Get - matching =0')
        # df = pdQuery.fullDeDupR1(id_inspection)
        print("allPD.view","*"*20)
        df = pdQuery.fullDeDupR1(id_inspection)
        print("allPD.view1", "*" * 20)
        df = df[['rack','AGVpos','codeUnit','nivel_y','Ppic']]
        description = ['rack', 'AGVpos', 'codeUnit', 'N','pic']
    else:
        'True to debug. and export file on DecodeMach'
        if 'fullDATA' in request.GET:

            df = pdQuery.decodeMach(id_inspection,False)
        else:

            df = pdQuery.decodeMach(id_inspection,False)

        #################################################################
        #EXPORT FULL INFO TO DEBUG
            # df.to_excel("resMergeWms.xlsx", sheet_name='ddp_dfwms_onCodeUnit-wmsProduct')
        ###################################################################

        df = df[['rack','wmsProduct','codeUnit','nivel_y','AGVpos','wmsPosition','wmsDesc','wmsDesc1','wmsDesc2','match','Ppic']]
        description = ['rack','wmsProduct','codeUnit','N','AGVpos','wmsPos','wmsDesc','wmsDesc1','wmsDesc2','c','pic']


    data = df.values.tolist()
    # description = list(df.columns.values)
    # print("data:"*10)
    # print(df.empty)

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
    # query = "SELECT distinct SUBSTRING(codePos,1,12) from inventorymaptbl where id_inspection = "+id_inspection+" AND codePos not like '%XX%';"
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
            # print("009")

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=exportedData_'+str(id_inspection)+'.csv'
            # print("010")

            df.to_csv(path_or_buf=response, sep=',', float_format='%.2f', index=False, decimal=".")

            messages.success(request, 'Data Exported ')

            return response

    # print("011")
    inspectionData = querys.getInspectionData(request.GET['id_inspection'])[0][0]
    dataLenght = len(data)-1
    # print("data: ",data)
    # print("len: ",len(data))
    # print(data[dataLenght][1])
    if not df.empty:
        lastReadQuery = "select substring(codePos,5,6) from inventorymaptbl where id_inspection = "+str(id_inspection)+" and codePos not like '' order by id_Vector desc limit 1;"
        lastRead = querys.mysqlQuery(lastReadQuery)[0][0][0]
        lastRead = "Aisle:"+lastRead[0:3]+ " Pos:"+lastRead[3:6]
    # print(lastRead)

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
               'inspection': inspectionData ,
               'picpath': picpath,
               'levels': levels,
               'lastRead':lastRead
               }

    return render(request, 'allPD.html', context)

@login_required(login_url="/login/")
def allPDvr(request):
    # dvr =pdQuery.virtualRack(98)
    # print(dvr)
    # dfpm10=pdQuery.plusminus10Pos(98,"UBG1002002")


    picpath = []
    levels = []
    lastRead =0
    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = "+str(id_inspection))[0][0][0]
    if request.GET['matching'] == '0':
        # print('in Get - matching =0')
        # df = pdQuery.fullDeDupR1(id_inspection)
        # print("allPD.view","*"*20)
        df = pdQuery.runningPosVR(id_inspection)
        print("allPD.view1", "*" * 20)
        df = df[['vRack','pos','codeUnit','nivel','picPath']]
        description = ['rack', 'AGVpos', 'codeUnit', 'N','pic']
        print("runningPosVR-completed: ",df)
    else:
        df = pdQuery.decodeMachPAVR(id_inspection)
        df = df.fillna('')
        #################################################################
        #EXPORT FULL INFO TO DEBUG
            # df.to_excel("resMergeWms.xlsx", sheet_name='ddp_dfwms_onCodeUnit-wmsProduct')
        ###################################################################


        validationQuery = "select * from validationtbl where id_inspection = " + str(
            id_inspection) + " order by id_validation;"
        dfv= pdQuery.pdDF(validationQuery)
        dfv = dfv.drop_duplicates(subset='product', keep='last')
        dfv
        df['verified'] = df.apply(
            lambda x: dfv['validation'][dfv['product'] == x['codeUnit']].tolist()[0] if x['codeUnit'] in dfv[
                'product'].tolist() else False, axis=1)
        print(df[df.wmsProduct.isin(dfv['product'].tolist())])

        # print(df)
        df = df[['verified','wmsProduct','codeUnit','nivel','pos','wmsPosition','wmsDesc','wmsDesc1','wmsdesc2','match','picPath']]
        description = ['vf','wmsProduct','codeUnit','N','AGVpos','wmsPos','wmsDesc','wmsDesc1','wmsDesc2','c','pic']


    data = df.values.tolist()
    # description = list(df.columns.values)
    # print("data:"*10)
    # print(df.empty)

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
    # query = "SELECT distinct SUBSTRING(codePos,1,12) from inventorymaptbl where id_inspection = "+id_inspection+" AND codePos not like '%XX%';"
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
            # print("009")

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=exportedData_'+str(id_inspection)+'.csv'
            # print("010")

            df.to_csv(path_or_buf=response, sep=',', float_format='%.2f', index=False, decimal=".")

            messages.success(request, 'Data Exported ')

            return response

    # print("011")
    inspectionData = querys.getInspectionData(request.GET['id_inspection'])[0][0]
    dataLenght = len(data)-1
    # print("data: ",data)
    # print("len: ",len(data))
    # print(data[dataLenght][1])
    if not df.empty:
        lastReadQuery = "select substring(codePos,5,6) from inventorymaptbl where id_inspection = "+str(id_inspection)+" and codePos not like '' order by id_Vector desc limit 1;"
        lastRead = querys.mysqlQuery(lastReadQuery)[0][0][0]
        lastRead = "Aisle:"+lastRead[0:3]+ " Pos:"+lastRead[3:6]
    # print(lastRead)
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
               'inspection': inspectionData ,
               'picpath': picpath,
               'levels': levels,
               'lastRead':lastRead
               }

    return render(request, 'allPD.html', context)


@login_required(login_url="/login/")
def allVR_noPD(request):
    # dvr =pdQuery.virtualRack(98)
    # print(dvr)
    # dfpm10=pdQuery.plusminus10Pos(98,"UBG1002002")


    picpath = []
    levels = []
    lastRead =0
    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = "+str(id_inspection))[0][0][0]
    if request.GET['matching'] == '0':
        # print('in Get - matching =0')
        # df = pdQuery.fullDeDupR1(id_inspection)
        # print("allPD.view","*"*20)
        df = pdQuery.runningPosVR(id_inspection)
        print("allPD.view1", "*" * 20)
        df = df[['vRack','pos','codeUnit','nivel','picPath']]
        description = ['rack', 'AGVpos', 'codeUnit', 'N','pic']
        # print("runningPosVR-completed: ",df)
    else:

        df = pdQuery.decodeMachVR_noPD(id_inspection)
        df = df.fillna('')
        #################################################################
        #EXPORT FULL INFO TO DEBUG
            # df.to_excel("resMergeWms.xlsx", sheet_name='ddp_dfwms_onCodeUnit-wmsProduct')
        ###################################################################


        validationQuery = "select * from validationtbl where id_inspection = " + str(
            id_inspection) + " order by id_validation;"
        dfv= pdQuery.pdDF(validationQuery)
        dfv = dfv.drop_duplicates(subset='product', keep='last')

        df['verified'] =""
        df['verified'] = df.apply(
            lambda x: dfv['validation'][dfv['product'] == x['codeUnit']].tolist()[0] if x['codeUnit'] in dfv[
                'product'].tolist() else False, axis=1)
        # print(df[df.wmsProduct.isin(dfv['product'].tolist())])

        #print(df.columns)
        df = df[['verified','wmsProduct','codeUnit','nivel','pos','wmsPosition','wmsDesc','wmsDesc1','wmsdesc2','match','desc','picPath']]
        description = ['vf','wmsProduct','codeUnit','N','AGVpos','wmsPos','D1','Description','D2','c','desc','p']

        if request.GET['matching']=='2':
            print('here')
            df = df[df['match']==False]

    data = df.values.tolist()
    # description = list(df.columns.values)
    # print("data:"*10)
    # print(df.empty)

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
    # query = "SELECT distinct SUBSTRING(codePos,1,12) from inventorymaptbl where id_inspection = "+id_inspection+" AND codePos not like '%XX%';"
    readedPositions = querys.mysqlQuery(query)[0][0][0]
    # print('readedPositions',readedPositions)
    query = "select count(distinct(codeUnit)) from inventorymaptbl where codeUnit not like ''  and id_inspection=" + str(id_inspection)
    readedCount = querys.mysqlQuery(query)[0][0][0]

    # print('readedCount',readedCount)
    # print(data)
    readedRatio = 0


    if int(readedCount) > 0:
        if readedPositions>0:
            readedRatio = round(readedCount / readedPositions, 2) * 100
        # print('readedRatio',readedRatio)


    warehouseRatio = 0
    # print(warehouseTotalPositions)
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
            # print("009")

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=exportedData_'+str(id_inspection)+'.csv'
            # print("010")

            df.to_csv(path_or_buf=response, sep=',', float_format='%.2f', index=False, decimal=".")

            messages.success(request, 'Data Exported ')

            return response


    # print("011")
    inspectionData = querys.getInspectionData(request.GET['id_inspection'])[0][0]
    dataLenght = len(data)-1
    # print("data: ",data)
    # print("len: ",len(data))
    # print(data[dataLenght][1])
    if not df.empty:
        lastReadQuery = "select substring(codePos,5,6) from inventorymaptbl where id_inspection = "+str(id_inspection)+" and codePos not like '' order by id_Vector desc limit 1;"
        lastRead = querys.mysqlQuery(lastReadQuery)[0][0][0]
        lastRead = "Aisle:"+lastRead[0:3]+ " Pos:"+lastRead[3:6]
    # print(lastRead)

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
               'inspection': inspectionData ,
               'picpath': picpath,
               'levels': levels,
               'lastRead':lastRead,
               'falsePAlist':df['codeUnit'][(df['match']==False) & (df['codeUnit'].str.len()>0)].tolist() if int(request.GET['matching'])>0 else ""

               }

    return render(request, 'allPD.html', context)

@login_required(login_url="/login/")
def allVR_noPD_1(request):
    # dvr =pdQuery.virtualRack(98)
    # print(dvr)
    # dfpm10=pdQuery.plusminus10Pos(98,"UBG1002002")


    picpath = []
    levels = []
    lastRead =0
    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = "+str(id_inspection))[0][0][0]
    if request.GET['matching'] == '0':
        # print('in Get - matching =0')
        # df = pdQuery.fullDeDupR1(id_inspection)
        # print("allPD.view","*"*20)
        df = pdQuery.runningPosVR(id_inspection)
        print("allPD.view1", "*" * 20)
        df = df[['vRack','pos','codeUnit','nivel','picPath']]
        description = ['rack', 'AGVpos', 'codeUnit', 'N','pic']
        # print("runningPosVR-completed: ",df)
    else:

        df = pdQuery.decodeMachVR_noPD_levels_sorted(id_inspection)
        df = df.fillna('')
        #################################################################
        #EXPORT FULL INFO TO DEBUG
            # df.to_excel("resMergeWms.xlsx", sheet_name='ddp_dfwms_onCodeUnit-wmsProduct')
        ###################################################################


        validationQuery = "select * from validationtbl where id_inspection = " + str(
            id_inspection) + " order by id_validation;"
        dfv= pdQuery.pdDF(validationQuery)
        dfv = dfv.drop_duplicates(subset='product', keep='last')

        df['verified'] =""
        df['verified'] = df.apply(
            lambda x: dfv['validation'][dfv['product'] == x['codeUnit']].tolist()[0] if x['codeUnit'] in dfv[
                'product'].tolist() else False, axis=1)
        # print(df[df.wmsProduct.isin(dfv['product'].tolist())])

        #print(df.columns)
        df = df[['verified','wmsProduct','codeUnit','nivel','pos','wmsPosition','wmsDesc','wmsDesc1','wmsdesc2','match','desc','picPath']]
        description = ['vf','wmsProduct','codeUnit','N','AGVpos','wmsPos','D1','Description','D2','c','desc','p']

        if request.GET['matching']=='2':

            df = df[(df['match']==False) & (df['wmsProduct']!='')]

        if request.GET['matching']=='3':

            df = df[(df['match']==False) & (df['wmsProduct']!='')]
            # print(df)
            try:
                df['waisle'] = df['wmsPosition'].str[4:7]
                df['wlevel'] = df['wmsPosition'].str[10:12]
                df['wpos'] = df['wmsPosition'].str[7:10]

            except:
                messages.warning(request,"There are values on Aisle, Level or Pos that brings conflicts. Sorry. Help us work around")
                # print("Something went wrong")
            # print(df)
            # print(df[['wmsPosition', 'wmsProduct', 'picPath', 'aisle', 'level', 'pos']])
            # table = pd.pivot_table(df[['wmsPosition', 'wmsProduct',  'aisle', 'level', 'pos','picPath']],index = ['aisle', 'level', 'pos'])
            # print(table.sort_values(['aisle', 'level', 'pos']))
            df = df[['waisle', 'wlevel', 'wpos','verified','wmsProduct','codeUnit','nivel','pos','wmsPosition',
                      'wmsDesc','wmsDesc1','wmsdesc2','match','desc',
                      'picPath']].sort_values(['waisle', 'wlevel', 'wpos'], ascending=[True,True,True])

            groups = df.groupby(['waisle', 'wlevel', 'wpos', 'wmsPosition', 'wmsProduct', 'pos', 'codeUnit']).size()
            groups = pd.DataFrame(groups)
            groups.drop(0,inplace=True,axis=1)

            context = {
                    'data': df.values.tolist(),
                    'groups':groups.to_html(border=0,classes='table table-head-fixed table-striped table-sm table-hover text-right', table_id = 'fails_by_aisle'),
                   'data1':df.to_html(),
                   'description': df.columns.tolist(),
                   'clientName': request.user.profile.client,
                   'id_warehouse': id_warehouse,
                   'warehouseName': querys.getWarehouseName(request.GET['id_inspection']),
                   'fail_count': df.shape[0],
                   'picpath': picpath,
                   'levels': levels,
                   'lastRead': lastRead,
                   'falsePAlist': df['codeUnit'][
                       (df['match'] == False) & (df['codeUnit'].str.len() > 0)].tolist() if int(
                       request.GET['matching']) > 0 else ""

                   }

            # return render(request, 'fail_by.html', context)

    data = df.values.tolist()


    # description = list(df.columns.values)
    # print("data:"*10)
    # print(df.empty)



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
    # query = "SELECT distinct SUBSTRING(codePos,1,12) from inventorymaptbl where id_inspection = "+id_inspection+" AND codePos not like '%XX%';"
    readedPositions = querys.mysqlQuery(query)[0][0][0]
    # print('readedPositions',readedPositions)
    query = "select count(distinct(codeUnit)) from inventorymaptbl where codeUnit not like ''  and id_inspection=" + str(id_inspection)
    readedCount = querys.mysqlQuery(query)[0][0][0]

    # print('readedCount',readedCount)
    # print(data)
    readedRatio = 0


    if int(readedCount) > 0:
        if readedPositions>0:
            readedRatio = round(readedCount / readedPositions, 2) * 100
        # print('readedRatio',readedRatio)


    warehouseRatio = 0
    # print(warehouseTotalPositions)
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
            # print("009")

            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=exportedData_'+str(id_inspection)+'.csv'
            # print("010")

            df.to_csv(path_or_buf=response, sep=',', float_format='%.2f', index=False, decimal=".")

            messages.success(request, 'Data Exported ')

            return response


    # print("011")
    inspectionData = querys.getInspectionData(request.GET['id_inspection'])[0][0]
    dataLenght = len(data)-1
    # print("data: ",data)
    # print("len: ",len(data))
    # print(data[dataLenght][1])
    if not df.empty:
        lastReadQuery = "select substring(codePos,5,6) from inventorymaptbl where id_inspection = "+str(id_inspection)+" and codePos not like '' order by id_Vector desc limit 1;"
        lastRead = querys.mysqlQuery(lastReadQuery)[0][0][0]
        lastRead = "Aisle:"+lastRead[0:3]+ " Pos:"+lastRead[3:6]
    # print(lastRead)

    context = {'data':data,

               # 'description':description,
               'description':df.columns.tolist(),
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
               'inspection': inspectionData ,
               'picpath': picpath,
               'levels': levels,
               'lastRead':lastRead,
               'falsePAlist':df['codeUnit'][(df['match']==False) & (df['codeUnit'].str.len()>0)].tolist() if int(request.GET['matching'])>0 else ""

               }

    if request.GET['matching']=='3':
        context['groups'] = groups.to_html(border=0,classes='table table-head-fixed table-striped table-sm table-hover text-right', table_id = 'fails_by_aisle')
        context['data1'] = df.to_html()
        return render(request, 'fail_by.html', context)
    return render(request, 'allPD.html', context)

@login_required(login_url="/login/")
def levelPics(request):
    picpath = []
    levels = []

    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = " + str(id_inspection))[0][0][0]
    # if id_inspection == 27 or id_inspection == 34:
    #     levelFactor = {1:0,2: 0, 3: 0, 4: 0.2, 5: 0.3}
    # else:
    #     levelFactor = {1:0,2: 0, 3: 0, 4: 0, 5:0,6:0,7:0,8:0}

    df = pdQuery.decodeMach(id_inspection, False)
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

    inspectionData =  querys.getInspectionData(request.GET['id_inspection'])[0][0]
    print("inspectionData",inspectionData)
    context = {'data': data,
               'description': description,
               'clientName': request.user.profile.client,
               'id_warehouse': id_warehouse,
               'warehouseName': querys.getWarehouseName(request.GET['id_inspection']),
               'inspection': inspectionData,
               'picpath': picpath,
               'levels': levels,
               }

    return render(request, 'levelPics.html', context)

@login_required(login_url="/login/")
def readedAnalysis(request):
    """
    The idea in this page is to show reliable info so when running an inspection we can understand
    what is going on on real time
    :param request:
    :return:

    """

    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = " + str(id_inspection))[0][0][0]
    wms_data = querys.mysqlQuery("select count(distinct wmsposition) from wmspositionmaptbl where id_inspection = "+str(id_inspection))[0][0][0]
    jsonData = []
    reqAsile = request.GET['asile']
    reqLevel = request.GET['level']
    if wms_data > 0:
        jsonData = pdQuery.agregates(id_inspection,reqAsile,reqLevel)
        # print(jsonData)
        barDict = json.loads(jsonData[0])
    else:
        jsonData = pdQuery.readAggregate(id_inspection)
        barDict = json.loads(jsonData[0])

    # print(jsonData,type(jsonData))
    # print("barDict: ",barDict)
    # ORGANIZO LAS SERIES PARA DATASETS DE CHART.JS NO VAN EN PARES SINO EN SETS DIFERENTES
    sd = []
    totalDatasets = len(barDict["data"][0])
    # print("totalDatasets:",totalDatasets)
    for i in range(0,totalDatasets):
        sd.append([])
    for item in barDict["data"]:

        for index,value in enumerate(item):
            # print(value,index)
            sd[index].append(value)
    #####################################################
    ## para el chart agregado por nivel
    ##############################################
    barLevelDict = json.loads(jsonData[1])
    # print("barLevelDict: ",barLevelDict)
    # ORGANIZO LAS SERIES PARA DATASETS DE CHART.JS NO VAN EN PARES SINO EN SETS DIFERENTES
    sdLevel = []
    totalDatasets = len(barLevelDict["data"][0])
    # print("totalDatasets:",totalDatasets)
    for i in range(0, totalDatasets):
        sdLevel.append([])
    for item in barLevelDict["data"]:

        for index, value in enumerate(item):
            # print(value,index)
            sdLevel[index].append(value)
    #####################################################
    # print(sd)
    table = []
    # print(barDict["index"])
    for index,row in enumerate(barDict["index"]):
        # print("index,row",index,row,sd[0])
        # print(sd)

        table.append([row,sd[0][index],sd[1][index],sd[2][index],int(sd[0][index])-int(sd[1][index])])

    # print("table",table)
    context = {
            'barSeries':barDict["columns"],
            'barX':barDict["index"],
            'barDataSets': sd,
            'table':table,
            'barLevelSeries':barLevelDict["columns"],
            'barLevelX': barLevelDict["index"],
            'barLevelDataSets': sdLevel,
            'wmsDataBool': True if wms_data>0 else False,
            'levels': barLevelDict["index"],
            'asiles': barDict["index"],
            'inspection': querys.getInspectionData(request.GET['id_inspection']),

    }

    return render(request, 'readedAnalysis.html', context)

@login_required(login_url="/login/")
def readedAnalysisVR(request):
    """
    The idea in this page is to show reliable info so when running an inspection we can understand
    what is going on on real time
    :param request:
    :return:

    """
    # print("readedAnalysisVR","1"*10,"*"*20)
    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = " + str(id_inspection))[0][0][0]
    wms_data = querys.mysqlQuery("select count(distinct wmsposition) from wmspositionmaptbl where id_inspection = "+str(id_inspection))[0][0][0]
    jsonData = []
    reqAsile = request.GET['asile']
    reqLevel = request.GET['level']
    # print("readedAnalysisVR","2"*10,"*"*20)

    if wms_data > 0:
        jsonData = pdQuery.agregatesVR(id_inspection,reqAsile,reqLevel)
        # print(jsonData)
        barDict = json.loads(jsonData[0])
    else:
        jsonData = pdQuery.readAggregate(id_inspection)
        barDict = json.loads(jsonData[0])

    # print(jsonData,type(jsonData))
    # print("barDict: ",barDict)
    # ORGANIZO LAS SERIES PARA DATASETS DE CHART.JS NO VAN EN PARES SINO EN SETS DIFERENTES
    sd = []
    totalDatasets = len(barDict["data"][0])
    # print("totalDatasets:",totalDatasets)
    # print("readedAnalysisVR", "3" * 10, "*" * 20)

    for i in range(0,totalDatasets):
        sd.append([])
    for item in barDict["data"]:

        for index,value in enumerate(item):
            # print(value,index)
            sd[index].append(value)
    #####################################################
    ## para el chart agregado por nivel
    ##############################################
    barLevelDict = json.loads(jsonData[1])
    # print("barLevelDict: ",barLevelDict)
    # ORGANIZO LAS SERIES PARA DATASETS DE CHART.JS NO VAN EN PARES SINO EN SETS DIFERENTES
    sdLevel = []
    totalDatasets = len(barLevelDict["data"][0])
    # print("totalDatasets:",totalDatasets)
    for i in range(0, totalDatasets):
        sdLevel.append([])
    for item in barLevelDict["data"]:

        for index, value in enumerate(item):
            # print(value,index)
            sdLevel[index].append(value)
    #####################################################
    # print(sd)
    table = []
    # print(barDict["index"])
    for index,row in enumerate(barDict["index"]):
        # print("index,row",index,row,sd[0])
        # print(sd)

        table.append([row,sd[0][index],sd[1][index],sd[2][index],int(sd[0][index])-int(sd[1][index])])

    # print("table",table)
    context = {
            'barSeries':barDict["columns"],
            'barX':barDict["index"],
            'barDataSets': sd,
            'table':table,
            'barLevelSeries':barLevelDict["columns"],
            'barLevelX': barLevelDict["index"],
            'barLevelDataSets': sdLevel,
            'wmsDataBool': True if wms_data>0 else False,
            'levels': barLevelDict["index"],
            'asiles': barDict["index"],
            'inspection': querys.getInspectionData(request.GET['id_inspection']),

    }
    # print("readedAnalysisVR","end"*10,"*"*20)

    return render(request, 'readedAnalysis.html', context)

@login_required(login_url="/login/")
def readedAnalysisVR_noPD(request):
    """
    The idea in this page is to show reliable info so when running an inspection we can understand
    what is going on on real time
    :param request:
    :return:

    """
    # print("readedAnalysisVR","1"*10,"*"*20)
    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = " + str(id_inspection))[0][0][0]
    wms_data = querys.mysqlQuery("select count(distinct wmsposition) from wmspositionmaptbl where id_inspection = "+str(id_inspection))[0][0][0]
    jsonData = []
    reqAsile = request.GET['asile']
    reqLevel = request.GET['level']
    # print("readedAnalysisVR","2"*10,"*"*20)

    if wms_data > 0:
        jsonData = pdQuery.agregatesVR(id_inspection,reqAsile,reqLevel)
        # print(jsonData)
        barDict = json.loads(jsonData[0])
    else:
        jsonData = pdQuery.readAggregate(id_inspection)
        barDict = json.loads(jsonData[0])

    # print(jsonData,type(jsonData))
    # print("barDict: ",barDict)
    # ORGANIZO LAS SERIES PARA DATASETS DE CHART.JS NO VAN EN PARES SINO EN SETS DIFERENTES
    sd = []
    totalDatasets = len(barDict["data"][0])
    # print("totalDatasets:",totalDatasets)
    # print("readedAnalysisVR", "3" * 10, "*" * 20)

    for i in range(0,totalDatasets):
        sd.append([])
    for item in barDict["data"]:

        for index,value in enumerate(item):
            # print(value,index)
            sd[index].append(value)
    #####################################################
    ## para el chart agregado por nivel
    ##############################################
    barLevelDict = json.loads(jsonData[1])
    # print("barLevelDict: ",barLevelDict)
    # ORGANIZO LAS SERIES PARA DATASETS DE CHART.JS NO VAN EN PARES SINO EN SETS DIFERENTES
    sdLevel = []
    totalDatasets = len(barLevelDict["data"][0])
    # print("totalDatasets:",totalDatasets)
    for i in range(0, totalDatasets):
        sdLevel.append([])
    for item in barLevelDict["data"]:

        for index, value in enumerate(item):
            # print(value,index)
            sdLevel[index].append(value)
    #####################################################
    # print(sd)
    table = []
    # print(barDict["index"])
    for index,row in enumerate(barDict["index"]):
        # print("index,row",index,row,sd[0])
        # print(sd)

        table.append([row,sd[0][index],sd[1][index],sd[2][index],int(sd[0][index])-int(sd[1][index])])

    # print("table",table)
    context = {
            'barSeries':barDict["columns"],
            'barX':barDict["index"],
            'barDataSets': sd,
            'table':table,
            'barLevelSeries':barLevelDict["columns"],
            'barLevelX': barLevelDict["index"],
            'barLevelDataSets': sdLevel,
            'wmsDataBool': True if wms_data>0 else False,
            'levels': barLevelDict["index"],
            'asiles': barDict["index"],
            'inspection': querys.getInspectionData(request.GET['id_inspection']),

    }
    # print("readedAnalysisVR","end"*10,"*"*20)

    return render(request, 'readedAnalysis.html', context)

@login_required(login_url="/login/")
def carrousel(request):
    picpath = []
    levels = []

    id_inspection = request.GET['id_inspection']
    id_warehouse = querys.mysqlQuery("select id_warehouse from inspectiontbl where id_inspection = " + str(id_inspection))[0][0][0]
    if id_inspection == 27 or id_inspection == 34:
        levelFactor = {1:0,2: 0, 3: 0, 4: 0.2, 5: 0.3}
    else:
        levelFactor = {1:0,2: 0, 3: 0, 4: 0, 5:0,6:0,7:0,8:0}

    df = pdQuery.decodeMach(id_inspection, False)
    # print("carrousel df,")
    # print(df.columns)
    df = df[
        ['rack', 'wmsProduct', 'codeUnit', 'nivel_y', 'AGVpos', 'wmsPosition', 'wmsDesc', 'wmsDesc1', 'wmsDesc2',
         'match','Wpic', 'Ppic','upic']]
    description = ['rack', 'wmsProduct', 'codeUnit', 'N', 'AGVpos', 'wmsPos', 'wmsDesc', 'wmsDesc1', 'wmsDesc2',
                   'c', 'pic']

    dfx = df[df["wmsPosition"].notnull()]
    print('dfx: ',dfx)
    dfa = dfx["wmsPosition"].str[4:7].unique()
    print("dfa",dfa)
    # pd.set_option("display.max_rows", None, "display.max_columns", None)
    # pd.reset_option('all')
    # print("dfx",dfx["wmsPosition"])
    dfl = dfx["wmsPosition"].str[10:12].unique()
    print("dfl: ",dfl)
    levels = dfl.tolist()
    print("levels: ",levels)
    if '' in levels:
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
    if '' in asiles:
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

    inspectionData = querys.getInspectionData(request.GET['id_inspection'])[0][0]

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
            'inspection':inspectionData,
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
            # print("myfile: ",myfile)
            if myfile != False:
                fs = FileSystemStorage()
                filename = fs.save(myfile.name,myfile)
                # print(  "aqui",filename)
                # uploaded_file_url = fs.url(filename)
                # print(uploaded_file_url)
                importBool = querys.importDataBulk(os.path.join(settings.MEDIA_ROOT,filename),id_inspection)
                # print("001")
                os.remove(os.path.join(settings.MEDIA_ROOT,filename))
                if importBool:
                    messages.success(request,"Your Data has been Imported correctly")
                else:
                    messages.error(request,"Check your file, we couldn't import it")
            else:
                messages.warning(request,"Please select a file to import")
        else:
            if 'Delete' in request.POST.keys():
                qy = "delete from wmspositionmaptbl where id_inspection = "+ id_inspection+"; "
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
               'inspection': querys.getInspectionData(request.GET['id_inspection']),

               }
    return render(request, 'importWMS.html', context)

@login_required(login_url="/login/")
def plusMinus(request):
    id_inspection = request.GET['id_inspection']
    id_unit = request.GET['id_unit'].strip()
    falseList=request.GET['list']
    agvPos = request.GET['agvPos'].strip()
    data = []
    dfw = pd.DataFrame
    validation = False
    falseIndex=0
    comment=""
    picPath=""

    wmsData = []
    pos=""
    unit=""
    # print("---------DATA-----")
    # print(id_unit,agvPos)
    #
    # print("lenfalseList: ",len(falseList),id_unit in falseList)
    # print(request.get_full_path())
    if len(falseList)>0:
        # print("falseList")

        falseList=falseList[1:-1].replace(" ","")
        falseList=falseList.replace("'","")
        falseList=falseList.split(",")

    if id_unit in falseList:
        print("id_unit in falseList")
        print(id_unit)
        falseIndex =falseList.index(id_unit)
        # print(falseIndex,falseList)

        validationQuery = "select * from validationtbl where product like '"+id_unit+"' and id_inspection = "+str(id_inspection)+" order by id_validation desc limit 1;"
        dfv=pdQuery.pdDF(validationQuery)
        if len(dfv)>0:
            messages.success(request,"Data Validated: " +str(dfv['validation'][0])+ " : "+ str(dfv['position'][0])+" , " + str(dfv['product'][0])+" : validated by "+ str(dfv['user'][0])+"    || Comments: "+str(dfv['comment'][0]))
            # print("Comment: ",str(dfv['comment'][0]))
            comment = dfv['comment'][0]
            validation = dfv['validation']

        if len(id_unit)>3:
            dfu = pdQuery.getRawDataByUnit(id_inspection, id_unit)
            data = dfu.values.tolist()
            unit = id_unit

            dfw = pdQuery.getWmsPosByUnit(id_inspection,id_unit)
            print("dfw--2",dfw)




    else:
        # print("0-------DFU----------")
        dfu,picPath = pdQuery.getRawDataByPos(id_inspection, agvPos)
        # print("-------DFU----------")
        # print("picPath")
        # print(dfu)

        if "wms" in request.get_full_path():
            dfw = pdQuery.getWmsPosByUnit(id_inspection, id_unit)

    if request.method == "POST":

        # print(request.POST.keys())

        if "comment" in request.POST.keys():
            if "acceptwms"in request.POST.keys():
                query = "insert into validationtbl (id_inspection,position,product,comment,user,validation) values ("+str(id_inspection)+",'"+str(dfw["wmsPosition"][0])+"','"+str(id_unit)+"','"+request.POST["comment"]+"','"+request.user.username+"','wms')"
                # print(str(dfw["wmsPosition"][0])," : : dfw['wmsPosition']")
                querys.execute(query)
            if "discrep"in request.POST.keys():
                query = "insert into validationtbl (id_inspection,position,product,comment,user,validation) values ("+str(id_inspection)+",'"+str(agvPos)+"','"+str(id_unit)+"','"+request.POST["comment"]+"','"+request.user.username+"','agv')"
                # query = "insert into validationtbl (id_inspection,position,product,comment,user,validation) values (1,'UBF1900890','PA33123','TEST VALUE','TESTUSER','wms')"
                querys.execute(query)

            messages.success(request,"PA - Validated. Thank you")
            # print('plusMinus?id_inspection='+str(id_inspection)+'&id_unit='+unit+'&agvPos='+str(agvPos))
            if 'wms' in request.get_full_path():
                return redirect(
                    '/plusMinus?id_inspection=' + str(id_inspection) + '&id_unit=' + unit + '&agvPos=' + str(
                        agvPos) + 'wms=1&list=' + str(falseList))
            return redirect('/plusMinus?id_inspection='+str(id_inspection)+'&id_unit='+unit+'&agvPos='+str(agvPos)+'&list='+str(falseList))


        if "position" in request.POST.keys():
            pos = request.POST["position"].strip()
            unit = request.POST["unit"].strip()

            # for key in request.POST.keys():
                # print(key,request.POST[key])


            if len(request.POST['position'])>= 10 :
                df = pdQuery.virtualRack(id_inspection)
                # print("Searching by pos:",pos)

                df['codePos_Sub'] = df['codePos'].apply(lambda x: x[0:10] if x is not None else x)

                index = df[df['codePos'].str[0:10] == pos][['rack', 'vRack', 'x', 'codePos']].index[0]
                # print(index)
                df[df['codePos'].str[0:10] == pos][['rack', 'vRack', 'x', 'codePos', 'codePos_Sub']]
                bottomindex = 0 if index - 8 < 1 else index - 8
                dfu =df.iloc[bottomindex:index + 20, [0, 1, 2, 5, 6, 7, 10, 15, 21, 22]]
                data = dfu.values.tolist()



            else:

                if len(request.POST['unit'])>= 7:
                    dfu = pdQuery.getRawDataByUnit(id_inspection,unit)
                    data = dfu.values.tolist()

                    dfw = pdQuery.getWmsPosByUnit(id_inspection, id_unit)
                    # print("*******DFW --"*8)
                    # print(dfw)


    # print("006")

    # print(dfv)
    if not id_unit == "" and "wms" not in request.get_full_path():
        # buscar foto por codeUnit
        # print("007")
        query = "select picPath from inventorymaptbl where id_inspection = " + id_inspection + " and codeUnit like '" + id_unit + "' ; "
        try:
            # print("007.1")
            picPath = querys.mysqlQuery(query)[0][0][0]
        except:
            # print("007.e")
            picPath = ""
    else:
        # buscar foto por codePos
        print("007.else")
        query = "select picPath from inventorymaptbl where id_inspection = " + id_inspection + " and codePos like '" + agvPos + "' ; "
        picPath = querys.mysqlQuery(query)[0][0][0]

    # print("%"*50)
    picPath = "media/smarti/"+str(id_inspection)+"/"+picPath
    # print('008__---')

    # print("picPath:","media/smarti/"+str(id_inspection)+"/"+picPath)
    if not "wms" in request.get_full_path():
        # print(dfw['wmsPosition'])
        pos = dfw['wmsPosition'][0]
        wmsPosAsLv = [pos[4:7],pos[7:10],pos[10:12]]
        agvPosAsLv = [agvPos[4:7],agvPos[7:10],pos[10:12]]
    else:
        wmsPosAsLv = [agvPos[4:7],agvPos[7:10],pos[10:12]]
        agvPosAsLv =wmsPosAsLv

    # print("agvPosAsLv",agvPosAsLv)
    #
    # print("falseList:",falseList)

    context = {"data": dfu.values.tolist(),
               "description":['id_Vector','rack','x','codePos','codeUnit','customCode3','nivel'],
               "lastSearchUnit":  unit,
               "lastSearchPos":pos,
               'inspection': querys.getInspectionData(request.GET['id_inspection']),
               'wmsData': dfw,
               'wmsPosAsLv': wmsPosAsLv,
               'agvPosAsLv': agvPosAsLv,
               'validation':validation,
               'comment':comment,
               'falsePAList': falseList,
               'falseIndex': falseIndex,
               'nextUnit': falseList[falseIndex+1] if falseIndex<len(falseList)-1 else unit,
               'backUnit': falseList[falseIndex-1] if falseIndex>0 else unit,
               'picPath':picPath,

               }
    return render(request, 'plusMinus.html', context)

@login_required(login_url="/login/")
def status(request):
    user = User.objects.get(username=request.user.username)  # get Some User.
    list_mails = ['miguel@kreometrology.com', 'bianchi.alejandro@hotmail.com']

    # print(user.groups.filter(name='driver').exists())
    if user.groups.filter(name='driver').exists():
        messages.success(request, "You are an authorized User of this device")
        id_device = request.GET['device']
        dfStatus,voltages,zero_status = pdQuery.getStatus(id_device)


        if len(dfStatus)>0:
            statusString = getStatusString(str(dfStatus['status'][0]))
            if "ex" in statusString:
                try:
                    if flags.flag_EX[id_device]:
                        utils.sendAlert(list_mails, "Alert!! - ScanBot EX:"+statusString)
                        flags.flag_EX[id_device] = False
                except:
                    flags.flag_EX[id_device] = True
            # statusString = str(dfStatus['status'][0])
            # print("003.0")
        else:
            # print("003.1")
            flags.flag_EX[id_device]=True
            statusString = "n/a"

        lastReadQuery = "select substring(codePos,5,6) as pos from inventorymaptbl where device like '" + str(id_device) \
                        + "' and codePos not like '' order by id_Vector desc limit 1;"
        lastRead = querys.mysqlQuery(lastReadQuery)
        # print("lastRead: ",lastRead[0][0][0])
        lastRead = "Aisle:" + lastRead[0][0][0][0:3] + " Pos:" + lastRead[0][0][0][3:6]
        # print("004")
        battery_24_limits = [24.4,25.4]
        battery_36_limits = [35.5,36.5]

        batteries = voltages.split(':')
        batteries[0] = float(batteries[0][:-2])
        batteries[1] = float(batteries[1][:-2])



        if batteries[0]< battery_24_limits[0]:
            batteries.append( "danger")
            try:
                if flags.flag_24v[id_device]:
                    utils.sendAlert(list_mails,"WARNING!! - 24v Battery Low")
                    flags.flag_24v[id_device]=False
            except:
                flags.flag_24v[id_device] = True

        elif batteries[0]>= battery_24_limits[0] and batteries[0]<= battery_24_limits[1]:
            flags.flag_24v[id_device] = True
            batteries.append( "warning")
        else:
            flags.flag_24v[id_device] = True
            batteries.append( "success")

        if batteries[1]< battery_36_limits[0]:
            batteries.append("danger")
            try:
                if flags.flag_36v[id_device]:
                    utils.sendAlert(list_mails,"WARNING!! - 36v Battery Low")
                    flags.flag_36v[id_device] = False
            except:
                flags.flag_36v[id_device] = True

        elif batteries[1]>= battery_36_limits[0] and batteries[1]<= battery_36_limits[1]:

            flags.flag_36v[id_device] = True
            batteries.append("warning")
        else:
            flags.flag_36v[id_device] = True
            batteries.append("success")


        distances = pdQuery.vBarDistances(id_device)
        # print("*--disntances--****"*3)
        # print(distances)
        last_id_inspection,start_time,end_time = pdQuery.lastInspectionTime(id_device)

        eleapsed_time = end_time['time']-start_time['time']
        # print("-------------TIME--------------")
        # print(eleapsed_time[0],type(eleapsed_time[0]))

        if start_time.empty:
            inspection_time = [last_id_inspection, "Didn't Start", "", ""]
        else:
            inspection_time = [last_id_inspection,start_time['time'][0],end_time['time'][0],eleapsed_time[0]]

        # print("inspection_time",inspection_time)
        context = {"status":dfStatus,
                   "statusSubstring":statusString,
                   "voltages":voltages,
                   "lastRead":lastRead,
                   "zero_status":zero_status,
                   "batteries":batteries,
                   "distances":distances.values.tolist(),
                   "vBar":distances.index.values.tolist(),
                   "time":inspection_time
                   }
        print(context)
        return render(request,"status.html",context)
    else:
        messages.success(request, "You are NOT authorized to this device")
        return redirect("/login/")




@login_required(login_url="/login/")
def devices(request):
    user = User.objects.get(username=request.user.username)  # get Some User
    print(user.username, user.groups.filter(name='driver').exists())
    if user.groups.filter(name='driver').exists():
        # print("here")
        messages.success(request, "You are an authorized User of this device")
        dfDevices = pdQuery.getDevices()
        data = dfDevices.values.tolist()
        description = dfDevices.columns.tolist()
        # print("data: ",data)
        # print("description:",description)

        context = {'data': data,
                   'description': description,

                   }

        return render(request, "devices.html", context)
    else:
        messages.success(request, "You are NOT authorized to this device")
        return redirect("/login/")



def getStatusString(lastAcation):
    # print("lastAcation: ",lastAcation)
    if lastAcation=="x":
        return "voltage"
    elif lastAcation[-1]=="p":
        return "Following Line"
    elif lastAcation=="s":
        return "Backwards"
    elif lastAcation=="w":
        return "forward"
    elif lastAcation=="a":
        return "Turning Left"
    elif lastAcation=="d":
        return "Turning Right"
    elif lastAcation == "0":
        return "Stopped"
    elif lastAcation == "Power On":
        return "Power On"
    else:

        return lastAcation



