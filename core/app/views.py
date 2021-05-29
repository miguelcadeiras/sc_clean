from django.shortcuts import render

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
        levelFactor = {2: 0, 3: 0, 4: 0, 5:  0}

    # levels = querys.getLevels(id_inspection)
    if request.GET['matching'] == '0':
        # print('in Get - matching =0')
        df = pdQuery.fullDeDup(id_inspection,levelFactor)
        df = df[['rack','AGVpos','codeUnit','nivel_y','Ppic']]
        description = ['rack', 'AGVpos', 'codeUnit', 'N','pic']

    else:
        'True to debug. and export file on DecodeMach'
        if 'fullDATA' in request.GET:
            df = pdQuery.decodeMach(id_inspection, levelFactor,True)
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
            for key in request.POST:
                print(key,request.POST[key])

            if request.POST['level']=="All":
                dff = df[df['level'].str.contains("2",na=False)]
                print(dff.shape())
            # dff = df[df['AGVpos'].str.contains(request.POST['asile']) & df['nivel_y'].astype('str').str.contains(request.POST['level'],na=false) & df['AGVpos'].str.contains(request.POST['position'])]
            data = dff.values.tolist()


        if 'exportData' in request.POST:
            response = HttpResponse(content_type='text/csv')
            response['Content-Disposition'] = 'attachment; filename=exportedData_'+str(id_inspection)+'.csv'

            df.to_csv(path_or_buf=response, sep=',', float_format='%.2f', index=False, decimal=".")

            messages.success(request, 'Data Exported ')

            return response

    context = {'data':data,
               'description':description,
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
               'picpath': picpath,
               'levels': levels,
               }

    return render(request, 'allPD.html', context)

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
