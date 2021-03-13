from django.shortcuts import render

# Create your views here.
from django.contrib.auth.models import User
from django.contrib.auth.decorators import login_required
from django.shortcuts import render, get_object_or_404, redirect
from django.template import loader
from django.http import HttpResponse
from django import template

from . import querys
from .models import *


@login_required(login_url="/login/")
def index(request):

    levels = querys.getLevels()
    clientUser = request.user.profile.client

    id_client,cols = querys.getClientID(clientUser)
    print(id_client[0][0])
    data, description = querys.getWarehouses(id_client[0][0])

    context = {'data':data,
               'description':description,
               'client':clientUser,

               'levels': levels,
               }

    return render(request,'warehouses.html',context)

@login_required(login_url="/login/")
def inspections(request):

    levels = querys.getLevels()
    clientUser = request.user.profile.client

    id_client,cols = querys.getClientID(clientUser)
    print(id_client[0][0])
    data, description = querys.getInspections(request.GET['id_warehouse'])

    context = {'data':data,
               'description':description,
               'client':clientUser,

               'levels': levels,
               }

    return render(request,'inspections.html',context)


@login_required(login_url="/login/")
def all(request):
    data,description = querys.getMatch(0,300)
    picpath = []
    levels = querys.getLevels()

    for row in data:
        picpath.insert(0,"assets/smarti/VisionBar0_rack_"+str(row[0]).zfill(8)+"_2021-01-10.bmp")

    # print(len1,description, picpath)
    id_inspection = request.GET['id_inspection']
    query = 'select count(wmsposition) from wmspositionmaptbl where id_inspection='+str(id_inspection)

    warehouseTotalPositions = querys.mysqlQuery(query)[0][0][0]
    print( 'warehouseTotalPositions',warehouseTotalPositions)
    query = "select count(wmsProduct) from wmspositionmaptbl where wmsproduct not like '' and id_inspection="+str(id_inspection)

    warehouseTotalCount = querys.mysqlQuery(query)[0][0][0]
    print('warehouseTotalCount',warehouseTotalCount)
    query = "select count(distinct(codePos)) from inventorymaptbl where codePos not like '' and id_inspection="+str(id_inspection)
    readedPositions = querys.mysqlQuery(query)[0][0][0]
    print('readedPositions',readedPositions)
    query = "select count(unit) from runningPositions where unit not like '' and id_inspection="+str(id_inspection)
    readedCount = querys.mysqlQuery(query)[0][0][0]
    print('readedCount',readedCount)
    # print(data)
    context = {'data':data,
               'clientName': request.user.profile.client,
               'warehouseName': querys.getWarehouseName(request.GET['id_inspection']),
               'warehouseTotalPositions':warehouseTotalPositions,
               'warehouseTotalCount': warehouseTotalCount,
               'warehouseRatio': round(warehouseTotalCount/warehouseTotalPositions,2)*100,
               'readedPositions':readedPositions,
               'readedCount':readedCount,
               'readedRatio':round(readedCount/readedPositions,2)*100,
               'inspection':querys.getInspectionData(request.GET['id_inspection']),
               'description':description,
               'picpath':picpath,
               'levels': levels,
               }

    return render(request,'all.html',context)

@login_required(login_url="/login/")
def level(request):
    nivel = request.GET['level']
    data,description = querys.unitsByLevel(nivel)
    positions,units = querys.levelOcupation(nivel)
    # print(positions,units)
    ocupation = int(units) / int(positions)
    # print("{:.2f}".format(ocupation*100))
    picpath = []
    levels = querys.getLevels()

    for row in data:
        picpath.insert(0,"assets/smarti/VisionBar0_rack_"+str(row[0]).zfill(8)+"_2021-01-10.bmp")

    # print(len1,description, picpath)
    # print(data)
    context = {'data':data,
               'description':description,
               'picpath':picpath,
               'levels': levels,
               'ocupation_ratio':"{:.2f}".format(ocupation*100),
               'ocupation':str(units),
               'positions':str(positions)
               }

    return render(request,'level.html',context)

def testPage(request):
    querys.connect()
    return render(request,'base.html',{})

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