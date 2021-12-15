import pandas as pd
import numpy as np
import mysql.connector as sql
import pymysql
from sqlalchemy import create_engine
import secrets
import openpyxl
from django.conf import settings
import socket
import matplotlib.pyplot as plt
from . import querys
import warnings

warnings.filterwarnings('ignore')

# # acceso al servidor remoto
# mysql_schema = 'inventory'
# mysql_user = 'smartcubik'
# mysql_password = 'Smartcubik1Root!'
# mysql_host = '151.106.108.129'
#
# # accesos a base local desarrollo
# mysql_schemaDev = 'inventory'
# mysql_userDev = 'webuser'
# mysql_passwordDev = 'Smartcubik1web'
# mysql_hostDev = 'localhost'

def engine():
    hostname = socket.gethostname()
    IPAddr = socket.gethostbyname(hostname)
    # print(IPAddr,hostname)
    # para debug cambio de != a ==
    if IPAddr == '151.106.108.129' :
        # print(" here")
        mysql_alchemyDevConString = 'mysql+pymysql://webuser:Smartcubik1web@127.0.0.1/inventory'
    else:
        # print(" 2here")
        mysql_alchemyDevConString = 'mysql+pymysql://smartcubik:Smartcubik1Root!@151.106.108.129/inventory'

    sqlEngine = create_engine(mysql_alchemyDevConString)

    return sqlEngine


def mysqlQuery(query):
    # print("in MysqlQuery")
    # print( query)
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    df = pd.read_sql(query, dbConnection)
    dbConnection.close()

    return df

# mysql_alchemyDevConString = secrets.mysql_alchemyDevConString

# print(secrets.mysql_schema)



# dbConnection = sqlEngine.connect()
# df = pd.read_sql("select * from inventorymapTbl where id_inspection=27", dbConnection)
# dbConnection.close()
# print(df)

def runningPositionsRaw(id_inspection):
    # cómo pasamos el virtual Rack.. aca.. con las queries estas.. para q funcione. 
    """
    method returns a pandas df
    :param id_inspection:
    :return:
    """
    posQuery = """ select distinct(codePos),(substring(codePos,1,10)) as Pos,rack,nivel,picPath as Ppic from inventorymaptbl 
    where id_inspection = """+str(id_inspection)+""" and
    length(codePos)>=12 and
    codePos not like 'UBG0%%' and
    substring(codePos,11,2) not like '01'
    group by rack
    order by rack asc, length(codePos) desc
    """

    unitsQuery = """ with fullRack as(
     select distinct rack from inventorymaptbl where id_inspection ="""+str(id_inspection)+"""
      )
      select fullRack.rack,x,codeUnit,nivel,camera,picpath as upic from fullRack left Join (
      select distinct(codeUnit),rack,x,nivel,camera,picpath from inventorymaptbl where id_inspection = """+str(id_inspection)+""") as units
      on fullRack.rack=units.rack 
      where codeunit not like ''
    	group by codeUnit
    """
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    dfUnits = pd.read_sql(unitsQuery, dbConnection)
    dfPos = pd.read_sql(posQuery, dbConnection)


    dbConnection.close()

    result = pd.merge(dfPos,
                      dfUnits,
                      on="rack",
                      how="outer"
                      )
    # result.to_excel("runningPositions.xlsx", sheet_name='Merge Data')
    # print(result.info())
    return result


def machingPositionsRaw(id_inspection):
    """
    if wmsData is pressent then returns matching positions without any
    correction or algorithm, just what we reead. No AI applied.
    :param id_inspection:
    :return:
    """
    rp = runningPositionsRaw(id_inspection)
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    dfwms = pd.read_sql(
        "select wmsPosition,wmsProduct,wmsDesc,wmsDesc1,wmsDesc2 from wmspositionmaptbl where id_inspection ="+str(id_inspection),
        dbConnection)

    dbConnection.close()
    resMergeWms = pd.merge(rp, dfwms, left_on="codeUnit", right_on="wmsProduct", how="outer")

    return resMergeWms


def correctionFactor(levelFactor,id_inspection):
    """

    :param dfRunningPositions:
    :param levelFactor:{5: 0.3, 4: 0.2, 3: 0, 2: 0}
    :param id_inspection:
    :return:
    """
    # uso un dictionary.. nivel: factor de corrección
    correctionFactor = levelFactor
    df = runningPositionsRaw(id_inspection)
    # df.to_excel("runningPositionsRaw.xlsx", sheet_name='right')

    # solo nos quedamos con los 6 digitos
    df['purePos'] = df['Pos'].str[4:]    # print(df)
    values = []
    modified = 0
    cfM = 0
    # print(values)
    # print("rerwrw",df["nivel_y"][2])
    for count, r in enumerate(df["purePos"]):
        purePos = float(r)

        if count == 0:
            # In [2]: '%03.f'%5
            # Out[2]: '005'

            values.append('%06.f' % purePos)
        else:
            x = df["x"][count]
            # print(df["nivel_x"][count],x)
            if pd.isna(df["nivel_y"][count]):
                cf = 0
            else:
                # print(correctionFactor)
                # print(float(df["nivel_y"][count]))
                cf = correctionFactor[float(df["nivel_y"][count])]


            # print("x",x,type(x),"cf",cf,type(cf),int(df["nivel_y"][count]))

            if x < cf or (x > 1.5 and x < 1.5 + cf):

                if (purePos % 2) == 0:

                    #                 print(purePos,purePos-2)
                    modified += 1
                    values.append('%06.f' % (purePos - 2))
                else:
                    #                 print(purePos,purePos+2)
                    modified += 1
                    values.append('%06.f' % (purePos + 2))
            else:
                values.append('%06.f' % (purePos))

    # print("modified Positions", modified, cfM, df["nivel_y"].count())
    # df2 = dfTest.assign(test=values)
    df2 = df.assign(algoPos=values)

    ## hasta aca corregimos la posición.. ahora hay que hacer el merge con el wms.
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    dfwms = pd.read_sql(
        "select wmsPosition,wmsProduct,wmsDesc,wmsDesc1,wmsDesc2 from wmspositionmaptbl where id_inspection =" + str(
            id_inspection),
        dbConnection)
    dbConnection.close()

    resMergeWms = pd.merge(df2, dfwms, left_on="codeUnit", right_on="wmsProduct", how="outer")

    # print(resMergeWms.head())
    # resMergeWms.to_excel("full_join_algo_r2.xlsx", sheet_name='Merge Data')

    return df2

def correctionFactorVR(levelFactor,id_inspection):
    # print("correctionFactorVR()","*"*20)
    """

    :param dfRunningPositions:
    :param levelFactor:{5: 0.3, 4: 0.2, 3: 0, 2: 0}
    :param id_inspection:
    :return:
    """
    # uso un dictionary.. nivel: factor de corrección
    correctionFactor = levelFactor
    # df = runningPositionsRaw(id_inspection)
    # print("correctionFactorVR()","1"*20)

    df = runningPosVR(id_inspection)

    # print("correctionFactorVR()","2"*20)

    # df.to_excel("runningPositionsRaw.xlsx", sheet_name='right')

    # solo nos quedamos con los 6 digitos
    df['purePos'] = df['Pos'].str[4:]    # print(df)
    values = []
    modified = 0
    cfM = 0
    # print(values)
    # print("rerwrw",df["nivel_y"][2])
    # print("correctionFactorVR()","3"*20)

    for count, r in enumerate(df["purePos"]):
        purePos = float(r)

        if count == 0:
            # In [2]: '%03.f'%5
            # Out[2]: '005'

            values.append('%06.f' % purePos)
        else:
            x = df["x"][count]
            # print(df["nivel_x"][count],x)
            if pd.isna(df["nivel_y"][count]):
                cf = 0
            else:
                # print(correctionFactor)
                # print(float(df["nivel_y"][count]))
                cf = correctionFactor[float(df["nivel_y"][count])]


            # print("x",x,type(x),"cf",cf,type(cf),int(df["nivel_y"][count]))

            if x < cf or (x > 1.5 and x < 1.5 + cf):

                if (purePos % 2) == 0:

                    #                 print(purePos,purePos-2)
                    modified += 1
                    values.append('%06.f' % (purePos - 2))
                else:
                    #                 print(purePos,purePos+2)
                    modified += 1
                    values.append('%06.f' % (purePos + 2))
            else:
                values.append('%06.f' % (purePos))

    # print("correctionFactorVR()","4"*20)

    # print("modified Positions", modified, cfM, df["nivel_y"].count())
    # df2 = dfTest.assign(test=values)
    df2 = df.assign(algoPos=values)

    return df2

def virtualRack(id_inspection):
    # print("virtualRack ()","*"*20)
    dfQuery = "select *  from inventorymaptbl where id_inspection = " + str(id_inspection) + "; "
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    df = pd.read_sql(dfQuery, dbConnection)
    dbConnection.close()

    midRack = False
    subdivisions = 2
    # defaultRlenght=2.75
    # rlength=2.75
    virtualRack = 50000

    # print(df.describe())
    df["ZERO"] = (df["customCode3"] == "ZERO")

    # calculo la mediana de las x de los ZEROS para el default. Excluimos los outliers
    defaultRlenght = df[(df["ZERO"]) & (df["x"] > 0.7) & (df["x"] < 3.8)].x.median()
    rlength = defaultRlenght

    df['rackLength'] = defaultRlenght
    df['vRack'] = 0

    count = len(df['x'])
    # print("COUNT:",count)
    for i, row in enumerate(df['x']):
        j = count - i - 1
        x = df['x'][j]

        if df['ZERO'][j]:
            midRack = True
            virtualRack += 1
            rlength = x

        if x < rlength / subdivisions and midRack:
            #         print("in mid",x,virtualRack)
            virtualRack += 1
            midRack = False

        df['rackLength'][j] = rlength
        #     df.loc[j,'rackLength']=rlength

        # si no tenemos ZEROS, NO PODEMOS HACER MÁS Q CONFIAR EN EL ENCODER.. DE MOMENTO
        if rlength > 1.5 * defaultRlenght:
            #         df.loc[j,'vRack']=df['rack'][j]
            df['vRack'][j] = df['rack'][j]
        else:
            df['vRack'][j] = virtualRack
    #          df.loc[j,'vRack']=virtualRack

    # print("virtualRack () -- END --","*"*20)

    return df

def runningPosVR(id_inspection):
    # print("runningPosVR()","*"*20)
    # tenemos q imprimir lo siguiente en pantalla
    # df = df[['rack', 'AGVpos', 'codeUnit', 'nivel_y', 'Ppic']]
    df =virtualRack(id_inspection)

    # OBTENGO SÓLO POSICIONES RECORRIDAS CON SU VIRTUAL RACK
    dfPos = df[["codePos", "vRack", "nivel"]]
    dfPos["pos"] = df["codePos"].str[0:10]
    dfPos = dfPos[(dfPos["codePos"].notnull()) & (dfPos["codePos"].str.len() > 0)]
    dfPos1 = dfPos[["pos", "vRack"]].drop_duplicates()
    # si pasamos 2 veces por la misma posición deberían haber 2 virtual Racks por posición
    # dfPos1.sort_values('pos')

    # OBTENGO LAS UNIDADES DETECTADAS CON SU VIRTUAL RACK
    dfUnits = df[["vRack", "x", "codeUnit", "visionBar", "nivel", "picPath"]]
    dfUnits = dfUnits[(dfUnits["codeUnit"].notnull()) & (dfUnits["codeUnit"].str.len() > 0)]
    dfUnits = dfUnits.drop_duplicates(subset="codeUnit", keep="first")
    # df.drop_duplicates(subset='A', keep="last")
    # dfUnits

    df_posUnits = pd.merge(dfPos1,
                    dfUnits,
                    left_on=["vRack"],
                    right_on=["vRack"],
                    how = "right"
                           )
    # print("runningPosVR() -- end --","*"*20)

    return df_posUnits


def plusminus10Pos(id_inspection,pos):
    df = virtualRack(id_inspection)
    # print("plusminus10Pos"+"---"*10)

    df['codePos_Sub'] = df['codePos'].apply(lambda x: x[0:10] if x is not None else x)
    # print("here")
    # print(df)
    index = df[df['codePos'].str[0:10] == pos][['rack', 'vRack', 'x', 'codePos']].index[0]
    # print(index)
    df[df['codePos'].str[0:10] == pos][['rack', 'vRack', 'x', 'codePos', 'codePos_Sub']]
    bottomindex = 0 if index - 8 < 1 else index - 8
    df2 = df.iloc[bottomindex:index + 15, [0, 1, 2, 5, 6, 7, 10, 15, 22, 23]]
    # print("plusminus10Pos"*5,df2)
    return df2

def plusminus10Unit(id_inspection,unit):
    df = virtualRack(id_inspection)

    index = df[df['codeUnit'] == unit][['rack', 'vRack', 'x', 'codeUnit']].index[0]
    # print(index)
    # df[df['codePos'].str[0:10] == pos][['rack','vRack','x','codePos','codePos_Sub']]
    bottomindex = 0 if index - 8 < 1 else index - 8
    df.iloc[bottomindex:index + 10, [0, 1, 2, 5, 6, 7, 10, 15, 22, 23]]
    df2 = df.iloc[bottomindex:index + 20, [0, 1, 2, 5, 6, 7, 10, 15, 22, 23]]
    # print(df2)
    return df2


def dedupMiddle(dfD, mid, th):
    """
    returns a new dataFrame, with deduplicated Rack values. Using AI to understand
    whether was on the next or before. It works only with simple sized pallets (double pallets positions are ignored).
    :param dfD: DF should be on one Level (ie, visionBar)
    :param mid: in mts, where should the rack cut.. usually 1.5
    :param th: threshold, used to define risk positions and start analisys just on those positions.
    :return:
    """
    for i in range(dfD.shape[0]):  # iterate over rows
        value = dfD.iloc[i]['x']  # get cell value
        pos = dfD.iloc[i]['algoPos']
        pa = dfD.iloc[i]['codeUnit']
        newPos = pos
        #         print("linea 2:" ,value,pos,pa,newPos,mid-th,mid+th)
        #         print("value:",value," cond1:" ,value>(mid-th)," cond2",value <(mid+th))

        if value > (mid - th) and value < (mid + th):
            #             print(value,pos,"even" if(int(pos) %2 ==0) else "odd")
            #             print(1001)
            newPos = pos

            if i == 0:
                testValue = dfD.iloc[1]['x']
                if (testValue > (mid - th) and testValue < (mid + th)):
                    #             en este caso tambien la segunda posicion esta en una de riesgo
                    #  la única logica qued puede haber es cual es leimos primero y cual despues
                    #                     print(1002)
                    pass

                else:
                    #           en este caso pasamos
                    #                     print(1003)
                    newPos = int(pos) - 2
                    pa = dfD.iloc[i]['codeUnit']
                    #                     print(1003,"pos",pos,"newPos",newPos)
                    return (newPos, pa)
            else:
                #                 print(1004)
                testValue = dfD.iloc[0]['x']
                if (testValue > (mid - th) and testValue < (mid + th)):
                    #             en este caso tambien la segunda posicion esta en una de riesgo
                    #  la única logica qued puede haber es cual es leimos primero y cual despues
                    #                     print(1005)
                    pass
                else:
                    #           en este caso pasamos
                    #                     print(1006,"pos",pos,"newPos",newPos)
                    newPos = int(pos) + 2
                    pa = dfD.iloc[i]['codeUnit']
                    #                     print(1007,"pos",pos,"newPos",newPos)
                    return (newPos, pa)

    return (newPos, pa)

def dedupMiddleR1(dfD):
    """
    returns a new dataFrame, with deduplicated Rack values. Using AI to understand
    whether was on the next or before. It works only with simple sized pallets (double pallets positions are ignored).
    :param dfD: DF should be on one Level (ie, visionBar)
    :param mid: in mts, where should the rack cut.. usually 1.5
    :param th: threshold, used to define risk positions and start analisys just on those positions.
    :return:
    """

    rack0 = dfD.iloc[0]['rack']
    x0 = dfD.iloc[0]['x']  # get cell value
    pos0 = int(dfD.iloc[0]['algoPos'])
    # print(pos0)
    pa0 = dfD.iloc[0]['codeUnit']

    rack1 = dfD.iloc[1]['rack']
    x1 = dfD.iloc[1]['x']  # get cell value
    pos1 = int(dfD.iloc[1]['algoPos'])
    pa1 = dfD.iloc[1]['codeUnit']

    if x0 < 1.5:
        if pos0 % 2 == 0:
            pos1 = pos0 + 2
        else:
            pos1 = pos0 - 2
        return pos1,pa1
    else:
        if pos0 % 2 == 0:
            pos0 = pos0 - 2
        else:
            pos0 = pos0 + 2
        return pos0,pa0


def fullDeDup(id_inspection, levelFactor):
    """
    :param id_inspection:
    :param mid: middle of the rack where it should change
    :param th: middle threshold
    :param levelFactor: dictionary for correction factor{level:cm,...,level_n:cm}
    :return: dataFrame
    """
    # print("levelFactor: ",levelFactor)
    df2 = correctionFactor(levelFactor, id_inspection)
    # obtengo los niveles de los datos corregidos
    dfNiveles = df2[df2["nivel_y"].notnull()]["nivel_y"].sort_values().unique().astype(int)
    # print(">>------")
    # print(dfNiveles)
    # separamos un df para cada nivel
    df_N = []
    for level in dfNiveles:
        df_N.append(df2[df2["nivel_y"] == level])

    # print(">>>>>>>>>>>>")
    # print(df_N)
    # print("<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>")


    # df_N5 = df2[df2["nivel_y"] == 5]
    # df_N4 = df2[df2["nivel_y"] == 4]
    # df_N3 = df2[df2["nivel_y"] == 3]
    # df_N2 = df2[df2["nivel_y"] == 2]

    for df in df_N:
        df_N2 = df[df["codePos"].str.len() <= 12]

        df2_duplicated = df_N2[df_N2.duplicated(['algoPos'])].sort_values(by=['algoPos'])
        # print (df2_duplicated["algoPos"])
        df2_duplicated = df2_duplicated[df2_duplicated.purePos.notnull()]
        # mid = 1.5
        # th = 0.2
        # df2Copy = df2.copy()

        # print("3.------------------")
        for rack in df2_duplicated["rack"]:
            dfDup = df_N2[df_N2['rack'] == rack]
            # print(dfDup[["algoPos","purePos","rack",'x','codeUnit']])


            if dfDup.shape[0] == 2:
                #       print(rack,dfDup['codePos'].str.len())
                oldPos = dfDup['algoPos'].values[0]
                # print(" >>s_______________<<< ")
                newPos, pa = dedupMiddleR1(dfDup)
                # print("dev:",newPos,pa)
                # print(" >>s_______________<<< ")
                # print(df2Copy[df2Copy["codeUnit"].str.contains(pa,na=False).values[0]])
                if oldPos != newPos:
                    try:
                        index = df.index[df["codeUnit"].str.contains(pa,na=False)].values[0]
                        # print(index)
                        df.at[index, 'algoPos'] = '%06.f' % (newPos)
                        # print(newPos, pa, oldPos, rack, dfDup['codeUnit'].values[0], dfDup['x'].values[0])
                    except:
                        pass

    print("<<<>>>>>Deduplication Completed Successfully<<<<>>>>>>")
    dfC = pd.concat(df_N)
    # dfC.describe()
    # dfC["AGVFullPos"] = 'UBG1' + dfC['algoPos'] + dfC['nivel_y']

    dfC["AGVpos"] = dfC['codePos'].str[:4] + dfC['algoPos'] + '0' + dfC["nivel_y"].fillna(0).astype(np.int8).astype(str)

    return dfC


def fullDeDupR1(id_inspection):
    """
    :param id_inspection:
    :param levelFactor: dictionary for correction factor{level:cm,...,level_n:cm}
    :param useDedup: use or Not the algorithm
    :return: dataFrame
    """
    # print("aasdfasdf -------------------------------------")
    levelFactor = querys.getLevelFactor(id_inspection)
    # print("LevelFactor: ->",levelFactor,type(levelFactor))

    #Chequeamos en la base de datos si usamos o no el Deduplicador y cuardamos en useDeDup
    useDeDup = querys.getUseDeDup(id_inspection)

    # print("useDeDupDebug","**"*30)
    print("useDeDup",useDeDup)
    # useDeDup=True
    df2 = correctionFactor(levelFactor, id_inspection)
    print(df2.columns)

    # obtengo los niveles de los datos corregidos
    dfNiveles = df2[df2["nivel_y"].notnull()]["nivel_y"].sort_values().unique().astype(int)
    # print(">>------")
    # print(dfNiveles)
    # separamos un df para cada nivel
    df_N = []
    for level in dfNiveles:
        df_N.append(df2[df2["nivel_y"] == level])

    # print(">>>>>>>>>>>>")
    # print(df_N)
    # print("<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>")


    # df_N5 = df2[df2["nivel_y"] == 5]
    # df_N4 = df2[df2["nivel_y"] == 4]
    # df_N3 = df2[df2["nivel_y"] == 3]
    # df_N2 = df2[df2["nivel_y"] == 2]

    for df in df_N:
        df_N2 = df[df["codePos"].str.len() <= 12]

        df2_duplicated = df_N2[df_N2.duplicated(['algoPos'])].sort_values(by=['algoPos'])
        # print (df2_duplicated["algoPos"])
        df2_duplicated = df2_duplicated[df2_duplicated.purePos.notnull()]
        # mid = 1.5
        # th = 0.2
        # df2Copy = df2.copy()

        # print("3.------------------")
        if useDeDup:
            print("usingDedup")
            for rack in df2_duplicated["rack"]:
                dfDup = df_N2[df_N2['rack'] == rack]
                # print(dfDup[["algoPos","purePos","rack",'x','codeUnit']])
                if dfDup.shape[0] == 2:
                    # print(rack,dfDup['codePos'].str.len())
                    oldPos = dfDup['algoPos'].values[0]
                    # print(" >>s_______________<<< ")
                    newPos, pa = dedupMiddleR1(dfDup)
                    # print("dev:",newPos,oldPos,pa)
                    # print(" >>s_______________<<< ")
                    # print(df2Copy[df2Copy["codeUnit"].str.contains(pa,na=False).values[0]])
                    if oldPos != newPos:
                        try:
                            index = df.index[df["codeUnit"].str.contains(pa,na=False)].values[0]
                            # print(index)
                            df.at[index, 'algoPos'] = '%06.f' % (newPos)
                            # print(newPos, pa, oldPos, rack, dfDup['codeUnit'].values[0], dfDup['x'].values[0])
                        except:
                            pass

            print("<<<>>>>>Deduplication Completed Successfully<<<<>>>>>>")
        else:
            print("<<<<<<<<<Deduplication Skipped>>>>>>>>>>>>>>>>>>>>>>>>")
    # print("df_N ---"*10)
    # print()

    if df_N!=[]:
        dfC = pd.concat(df_N)
    else:
        dfC = df2
    # print('back to df2')
    # dfC.describe()
    # dfC["AGVFullPos"] = 'UBG1' + dfC['algoPos'] + dfC['nivel_y']

    dfC["AGVpos"] = dfC['codePos'].str[:4] + dfC['algoPos'] + '0' + dfC["nivel_y"].fillna(0).astype(np.int8).astype(str)
    # print(dfC.columns)
    # print(dfC['AGVpos'])


    return dfC

def fullDeDupVR(id_inspection):
    """
    :param id_inspection:
    :param levelFactor: dictionary for correction factor{level:cm,...,level_n:cm}
    :param useDedup: use or Not the algorithm
    :return: dataFrame
    """
    # print("fullDeDupVR", "*" * 20)

    # print("aasdfasdf -------------------------------------")
    levelFactor = querys.getLevelFactor(id_inspection)
    # print("LevelFactor: ->",levelFactor,type(levelFactor))

    #Chequeamos en la base de datos si usamos o no el Deduplicador y cuardamos en useDeDup
    useDeDup = querys.getUseDeDup(id_inspection)

    print("useDeDupDebug","**"*30)
    print("useDeDup",useDeDup)
    # useDeDup = False
    df2 = correctionFactorVR(levelFactor, id_inspection)
    # print("correctionFactorVR..COMPLETED", "*" * 20)
    # print(df2.columns)
    df2["codePos"]= df2["pos"]+df2["_nivel"].astype(str)
    df2.rename(columns={"picPath_x":"Ppic"}, inplace=True)
    # print("rename","r"*15)
    # print(df2["Ppic"])
    # print(df2.columns)
    # obtengo los niveles de los datos corregidos
    dfNiveles = df2[df2["nivel_y"].notnull()]["nivel_y"].sort_values().unique().astype(int)
    # print(">>------")
    # print(dfNiveles)
    # separamos un df para cada nivel
    df_N = []
    for level in dfNiveles:
        df_N.append(df2[df2["nivel_y"] == level])

    # print(">>>>>>>>>>>>")
    # print(df_N)
    # print("<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>")


    # df_N5 = df2[df2["nivel_y"] == 5]
    # df_N4 = df2[df2["nivel_y"] == 4]
    # df_N3 = df2[df2["nivel_y"] == 3]
    # df_N2 = df2[df2["nivel_y"] == 2]

    for df in df_N:
        df_N2 = df[df["codePos"].str.len() <= 12]

        df2_duplicated = df_N2[df_N2.duplicated(['algoPos'])].sort_values(by=['algoPos'])
        # print (df2_duplicated["algoPos"])
        df2_duplicated = df2_duplicated[df2_duplicated.purePos.notnull()]
        # mid = 1.5
        # th = 0.2
        # df2Copy = df2.copy()

        print("3.------------------")
        if useDeDup:
            print("usingDedup")
            for rack in df2_duplicated["rack"]:
                dfDup = df_N2[df_N2['rack'] == rack]
                # print(dfDup[["algoPos","purePos","rack",'x','codeUnit']])
                if dfDup.shape[0] == 2:
                    # print(rack,dfDup['codePos'].str.len())
                    oldPos = dfDup['algoPos'].values[0]
                    # print(" >>s_______________<<< ")
                    newPos, pa = dedupMiddleR1(dfDup)
                    # print("dev:",newPos,oldPos,pa)
                    print(" >>s_______________<<< ")
                    # print(df2Copy[df2Copy["codeUnit"].str.contains(pa,na=False).values[0]])
                    if oldPos != newPos:
                        try:
                            index = df.index[df["codeUnit"].str.contains(pa,na=False)].values[0]
                            # print(index)
                            df.at[index, 'algoPos'] = '%06.f' % (newPos)
                            # print(newPos, pa, oldPos, rack, dfDup['codeUnit'].values[0], dfDup['x'].values[0])
                        except:
                            pass

            print("<<<>>>>>Deduplication Completed Successfully<<<<>>>>>>")
        else:
            print("<<<<<<<<<Deduplication Skipped>>>>>>>>>>>>>>>>>>>>>>>>")
    # print("df_N ---"*10)
    # print()

    if df_N!=[]:
        dfC = pd.concat(df_N)
    else:
        dfC = df2
    # print('back to df2')
    # dfC.describe()
    # dfC["AGVFullPos"] = 'UBG1' + dfC['algoPos'] + dfC['nivel_y']

    dfC["AGVpos"] = dfC['codePos'].str[:4] + dfC['algoPos'] + '0' + dfC["nivel_y"].fillna(0).astype(np.int8).astype(str)
    # print(dfC.columns)
    # print(dfC['AGVpos'])


    return dfC


def testFullDeDup(id_inspection, mid, th, levelFactor, rack):
    """
    :param id_inspection:
    :param mid: middle of the rack where it should change
    :param th: middle threshold
    :param levelFactor: dictionary for correction factor{level:cm,...,level_n:cm}
    :param rack: list of rack you want to check
    :return: dataFrame
    """

    df2 = correctionFactor(levelFactor, id_inspection)
    # obtengo los niveles de los datos corregidos
    df2 = df2[df2["rack"] == rack]
    print("0,,,,,,")
    print(df2[['rack','purePos','algoPos','codeUnit','x','nivel_y']])
    pass
    dfNiveles = df2[df2["nivel_y"].notnull()]["nivel_y"].sort_values().unique().astype(int)
    print(dfNiveles)
    # separamos un df para cada nivel
    df_N = []
    for level in dfNiveles:
        df_N.append(df2[df2["nivel_y"] == level])

    # print(">>>>>>>>>>>>")
    # print(df_N)
    # print("<<<<<<<<<<<<<>>>>>>>>>>>>>>>>>>>>>>>>>")


    # df_N5 = df2[df2["nivel_y"] == 5]
    # df_N4 = df2[df2["nivel_y"] == 4]
    # df_N3 = df2[df2["nivel_y"] == 3]
    # df_N2 = df2[df2["nivel_y"] == 2]
    # print("df_N:",df_N)
    for df in df_N:
        df_N2 = df[df["codePos"].str.len() <= 12]
        # print("df_N2:",df_N2)
        df2_duplicated = df_N2[df_N2.duplicated(['algoPos'])].sort_values(by=['algoPos'])
        # print("df2_duplicated:",df2_duplicated)
        # print(df2_duplicated["algoPos"])
        df2_duplicated = df2_duplicated[df2_duplicated.purePos.notnull()]
        # mid = 1.5
        # th = 0.2
        # df2Copy = df2.copy()

        # print("3.------------------")
        for rack in df2_duplicated["rack"]:
            dfDup = df_N2[df_N2['rack'] == rack]
            print("2,,,,,,")
            # print(dfDup[["algoPos","purePos","rack",'x','codeUnit']])


            if dfDup.shape[0] == 2:
                #       print(rack,dfDup['codePos'].str.len())
                oldPos = dfDup['algoPos'].values[0]
                print(" >>s_______________<<< ")
                newPos, pa = dedupMiddle(dfDup, mid, th)
                print("dev:",newPos,pa)
                # print(" >>s_______________<<< ")
                # print(df2Copy[df2Copy["codeUnit"].str.contains(pa,na=False).values[0]])
                print(" oldPos:",oldPos," newPOs:",newPos)
                print(oldPos == newPos)
                if oldPos != newPos:
                    index = df.index[df["codeUnit"].str.contains(pa,na=False)].values[0]
                    df.at[index, 'algoPos'] = '%06.f' % newPos
                    print(index)


                # print(newPos, pa, oldPos, rack, dfDup['codeUnit'].values[0], dfDup['x'].values[0])

    print("<<<>>>>>pd<<<<>>>>>>")

    return pd.concat(df_N)


def decodeMach(id_inspection,export_to_excel=False):
    # dfBeforeDeDup = correctionFactor(levelFactor, id_inspection)
    print("decodeMach()----")
    ddp = fullDeDupR1(id_inspection)
    # ddp = ddp.drop(columns='codePos')
    # print(".............DDP DATAFRAME")
    # print(".............DDP DATAFRAME")
    # print(".............DDP DATAFRAME")
    # print(ddp)
    # print(ddp.info())
    # ddp.to_excel("DDP.xlsx", sheet_name='Merge Data')

    #
    # juntamos las imagenes de las posiciones obtenidas con las del wms
    posFullQuery = """ select distinct codePos,picPath as Wpic from inventorymaptbl 
    where id_inspection = """ + str(id_inspection) + """
     and codePos not like '' and
     substring(codePos,11,2) not like '01' and
     substring(codePos,11,2) not like 'XX' AND
     substring(codePos,11,2) not like '00'
     group by codePos
     ;
    """

    wmsQuery = "select wmsPosition,wmsProduct,wmsDesc,wmsDesc1,wmsDesc2 from wmspositionmaptbl where id_inspection =" + str(
        id_inspection)
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    # print('geting df wms0 -----------------------------------')
    dfwms0 = pd.read_sql(wmsQuery, dbConnection)
    # print('end of dfwms0 -----------------------------------')
    # print('GETTING ... dfFullPos -----------------------------------')
    dfFullPos = pd.read_sql(posFullQuery,dbConnection)
    # print('dfFullPos -----------------------------------')
    dbConnection.close()
    # print(dfwms)
    #asigno aqui la foto para cada uno de en wPic para cada posicion.. sino en la otra query queda vacio

    # algo aca no esta funcionando ademas.. hay un problema con la cantidad de memoria que se utiliza.. explota el Web Server.
    dfwms = result = pd.merge(dfwms0,dfFullPos,
                  left_on="wmsPosition",
                  right_on="codePos",
                  how="outer"

                  )
    #quito de la memoria el otro df.. es muy grande.
    dfwms0 = []
    # print("dfwms---------------")
    # print("dfwms---------------")
    # print("dfwms---------------")
    # print("dfwms---------------")
    # print(dfwms)
    # dfwms.to_excel("dfwms.xlsx", sheet_name='Merge Data')
    # print(dfwms.info())
    # print(dfwms.describe())
    #### FIN JUNTADA DE IMAGENES ###
    # print("resMergeWms ------------------")
    # print("resMergeWms ------------------")
    # print("resMergeWms ------------------")
    # print("resMergeWms ------------------")



    dfwms = dfwms.drop(columns = 'codePos')
    # dfwms.to_excel("dfwms.xlsx", sheet_name='Merge Data')
    ddp = ddp.drop(columns = ['codePos','Pos','nivel_x'])
    # ddp.to_excel("DDP1.xlsx", sheet_name='Merge Data')

    resMergeWms = pd.merge(ddp, dfwms, left_on="codeUnit", right_on="wmsProduct", how="outer")
    # print("filter")
    # print("ResMerge INFO")
    # print(resMergeWms.info())
    resMergeWms = resMergeWms[resMergeWms['wmsPosition'].notnull()]
    # resMergeWms = resMergeWms[resMergeWms['b']==True]
    # resMergeWms.to_excel("resMergeWms.xlsx", sheet_name='ddp_dfwms_onCodeUnit-wmsProduct')
    # print("ResMerge DF")
    # print(resMergeWms)
    # print("ResMerge INFO")
    # print(resMergeWms.info())
    # print("ResMerge dESCRIBE")
    # print(resMergeWms.describe())
    # print("006")
    resMergeWms = resMergeWms.replace(np.nan, '', regex=True)
    # print("007")
    resMergeWms['double'] = resMergeWms['wmsPosition'].str.len() == 14

    # ARREGLO LOS MEDIO PALLETS.. COPIO LOS ÚLTIMOS 2 DE LA POSICION DEL WMS..
    # HABRIA QUE VERLO CON LA CAMARA.. QUE ESTA ANDANDO BIEN.. PERO HABRIA QUE ENTENDER LA LÓGICA.

    # resMergeWms
    # print("here")
    # df['name_match'] = df['First_name'].apply(lambda x: 'Match' if x == 'Bill' else 'Mismatch')
    # df.loc[df['First_name'] == 'Bill', 'name_match'] = 'Match'
    resMergeWms.loc[(resMergeWms['double'] == True) & (resMergeWms['AGVpos']!=''), 'AGVpos'] = resMergeWms['AGVpos'].astype('string') + resMergeWms['wmsPosition'].str[12:14]
    resMergeWms.loc[resMergeWms['double'] == False, 'AGVpos'] = resMergeWms['AGVpos']
    resMergeWms['AGVpos'] = resMergeWms['AGVpos'].replace(np.nan, '', regex=True)


    # print("double",resMergeWms[['double','wmsPosition','AGVpos','camera']])

    resMergeWms['match'] = resMergeWms['wmsPosition'].values == resMergeWms['AGVpos'].values
    # print(resMergeWms.describe())
    resMergeWms.loc[(resMergeWms.wmsProduct == '') & (resMergeWms.codeUnit == ''),"match"] = True
    # resMergeWms = resMergeWms[resMergeWms['wmsProduct'] != '']

    # print(resMergeWms[['wmsPosition','AGVpos','match']])
    # print("009")
    if export_to_excel:
        resMergeWms.to_csv("exportedData.csv")



    return resMergeWms

def decodeMachPAVR(id_inspection):
    # print("decodeMachVR() ---", "*"*15)
    df = virtualRack(id_inspection)

    # GETTING JUST POSITION and vRack
    dfPos = df[["codePos", "vRack", "nivel"]]
    # nos quedamos con los digitos de Posicion
    dfPos["pos"] = df["codePos"].str[0:10]
    # solo nos quedamos con las posiciones no nulas y vacías q tienen virtualRack
    dfPos = dfPos[(dfPos["codePos"].notnull()) & (dfPos["codePos"].str.len() > 0)]
    dfPos1 = dfPos[["pos", "vRack"]].drop_duplicates()
    dfPos1.sort_values('pos')

    # NOS QUEDAMOS CON EL TRUE-FALSE DE LOS PALLETS
    dfPallet = df[["vRack", "customCode3", "nivel", "picPath"]]
    dfPallet = dfPallet[(dfPallet["customCode3"].str.contains('PALLET', regex=False))]
    dfPallet['Pallet'] = (dfPallet["customCode3"].str.contains('TRUE', regex=False))
    del dfPallet["customCode3"]
    dfPallet.drop(dfPallet[dfPallet['vRack'] == 0].index, inplace=True)

    ## UNITS por vRack
    dfUnits = df[["vRack", "x", "codeUnit", "visionBar", "nivel", "picPath"]]
    dfUnits = dfUnits[(dfUnits["codeUnit"].notnull()) & (dfUnits["codeUnit"].str.len() > 0)]
    dfUnits = dfUnits.drop_duplicates(subset="codeUnit", keep="first")

    ###### COMENZAMOS CON LOS MERGE
    #UNIONES entre Pallets,vrack y Posiciones y Vrack
    df_posPallet = pd.merge(dfPos1, dfPallet, on=["vRack"], how="right")

    # UNION  CON ETIQUETAS DE CODE UNIT  (OUTER MERGE)

    dfResult = pd.merge(df_posPallet[["vRack", "nivel", "Pallet", "pos", "picPath"]],
                        dfUnits[["vRack", "x", "codeUnit", "visionBar", "nivel"]],
                        on=["vRack", "nivel"],
                        how="outer"
                        )

    #### CONECTAMOS AL WMS-IMPORTED
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    dfwms = pd.read_sql(
        "select wmsPosition,wmsProduct,wmsDesc,wmsDesc1,wmsdesc2 from wmspositionmaptbl where id_inspection =" + str(
            id_inspection), dbConnection)
    dbConnection.close()
    dfwms = dfwms.replace(r'^\s*$', np.nan, regex=True)
    dfwms["wPos"] = dfwms["wmsPosition"].str[4:10]
    dfwms["wmsPos"] = dfwms['wmsPosition'].str[0:10]

    ## HAY Q EVITAR LOS NAN.. entonces comparamos por separado,: donde hay prod, y donde No
    # DONDE HAY PRODUCTO
    df_testProduct = dfResult.dropna(subset=['codeUnit']) \
        .merge(dfwms.dropna(subset=['wmsProduct']),
               left_on='codeUnit',
               right_on='wmsProduct',
               how='outer')
    df_testProduct['aPos'] = df_testProduct['pos'].apply(lambda x: x[4:10] if x is not np.NaN else np.NaN)
    df_testProduct['match'] = df_testProduct.apply(lambda x: True if x['aPos'] == x['wPos'] else False, axis=1)

    # DONDE NO HAY PRODUCTO EN EL WMS

    df_noProduct = dfPos1.merge(dfwms[(dfwms['wmsProduct'].isna())], left_on='pos', right_on='wmsPos', how='right')
    df_noProduct['match'] = df_noProduct.apply(lambda x: True if x['pos'] == x['wmsPos'] else np.nan, axis=1)

    # UNIMOS LOS 2
    dfTotalMatch = df_testProduct.append(df_noProduct)
    # print("decodeMachVR() ---END ---", "*"*15)

    return dfTotalMatch

def decodeMachVR_noPD(id_inspection):
    df = virtualRack(id_inspection)

    # GETTING JUST POSITION and vRack
    dfPos = df[["codePos", "vRack", "nivel"]]
    # nos quedamos con los digitos de Posicion
    dfPos["pos"] = df["codePos"].str[0:10]
    # solo nos quedamos con las posiciones no nulas y vacías q tienen virtualRack
    dfPos = dfPos[(dfPos["codePos"].notnull()) & (dfPos["codePos"].str.len() > 0)]
    dfPos1 = dfPos[["pos", "vRack"]].drop_duplicates()
    # dfPos1.sort_values('pos')

    # EN ESTA SITUACIÓN NO TENEMOS INFORMACIÓN DE DETECCIÓN DE PALLETS.
    # # NOS QUEDAMOS CON EL TRUE-FALSE DE LOS PALLETS
    # dfPallet = df[["vRack", "customCode3", "nivel", "picPath"]]
    # dfPallet = dfPallet[(dfPallet["customCode3"].str.contains('PALLET', regex=False))]
    # dfPallet['Pallet'] = (dfPallet["customCode3"].str.contains('TRUE', regex=False))
    # del dfPallet["customCode3"]
    # dfPallet.drop(dfPallet[dfPallet['vRack'] == 0].index, inplace=True)

    ## UNITS por vRack
    dfUnits = df[["vRack", "x", "codeUnit", "visionBar", "nivel", "picPath"]]
    dfUnits = dfUnits[(dfUnits["codeUnit"].notnull()) & (dfUnits["codeUnit"].str.len() > 0)]
    dfUnits = dfUnits.drop_duplicates(subset="codeUnit", keep="first")

    ###### COMENZAMOS CON LOS MERGE
    #UNIONES entre UNITS ,vrack y Posiciones y Vrack
    df_posUnits = pd.merge(dfPos1,
                           dfUnits,
                           left_on=["vRack"],
                           right_on=["vRack"],
                           how="right"
                           )
    df_posUnits = df_posUnits.drop_duplicates(subset="codeUnit", keep="first")


    #### CONECTAMOS AL WMS-IMPORTED
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    dfwms = pd.read_sql(
        "select wmsPosition,wmsProduct,wmsDesc,wmsDesc1,wmsdesc2 from wmspositionmaptbl where id_inspection =" + str(
            id_inspection), dbConnection)
    dbConnection.close()
    dfwms = dfwms.replace(r'^\s*$', np.nan, regex=True)
    dfwms["wPos"] = dfwms["wmsPosition"].str[4:10]
    dfwms["wmsPos"] = dfwms['wmsPosition'].str[0:10]

    ## HAY Q EVITAR LOS NAN.. entonces comparamos por separado,: donde hay prod, y donde No
    # DONDE HAY PRODUCTO
    df_productsResult = pd.merge(df_posUnits, dfwms.dropna(subset=['wmsProduct']),
                                 how="right",
                                 left_on="codeUnit",
                                 right_on="wmsProduct")

    # DONDE NO HAY PRODUCTO EN EL WMS

    # merge de products where no son nan
    df_noProductTest = pd.merge(dfwms[dfwms['wmsProduct'].isna()], dfPos1["pos"],
                                how="left",
                                left_on="wmsPos",
                                right_on="pos")
    df_noProductTest = df_noProductTest.drop_duplicates(subset='wmsPosition')



    # UNIMOS LOS 2
    def reason(x):
        r = ""
        #     print(isinstance(x['aPos'],float) & isinstance(x['wmsProduct'],float))
        #     print(x['aPos'],type(x['aPos']),isinstance(x['aPos'],str))

        if x['pos'] == x['wmsPos']:
            r = "match"

        elif isinstance(x['codeUnit'], float):
            r = "not readed"
            if isinstance(x['aPos'], float) & isinstance(x['wmsProduct'], float):
                r = "n/a"
        elif x['pos'] == np.nan:
            r = "wait"



        elif isinstance(x['aPos'], str) & isinstance(x['wPos'], str):

            if abs(int(x['wPos']) - int(x['aPos'])) == 2:
                r = "2"
            else:
                r = "missMatch"

        #     print("r",r,"*"*25)
        return r

    dfResult_nPA = df_productsResult.append(df_noProductTest)
    dfResult_nPA['aPos'] = dfResult_nPA['pos'].str[4:10]
    dfResult_nPA['match']=False
    dfResult_nPA['desc'] =""

    dfResult_nPA['match'] = dfResult_nPA.apply(lambda x: True if x['pos'] == x['wmsPos'] else False, axis=1)

    dfResult_nPA['desc'] = dfResult_nPA.apply(lambda x: reason(x), axis=1)

    col_names = ['pos',
                 'wmsPos', 'vRack', 'x', 'wmsProduct', 'codeUnit', 'visionBar', 'nivel',
                 'wmsPosition', 'wmsDesc', 'wmsDesc1', 'wmsdesc2', 'wPos', 'aPos', 'match', 'desc', 'picPath']
    dfResult_nPA = dfResult_nPA.reindex(columns=col_names)


    return dfResult_nPA


def decodeMachVR(id_inspection, export_to_excel=False):
    return

def pasilloNivel(id_inspection,levelFactor,pasillo,nivel):
    df = decodeMach(id_inspection, False)
    pas = '%03.f' % pasillo
    dfPasNiv = df[
        df['wmsPosition'].str[4:7].str.contains(pas, na=False) & df['wmsPosition'].str[11:12].str.contains(str(nivel),
                                                                                                             na=False)]

    return dfPasNiv


# ########################################################################
def testing(id_inspection):

    wmsQuery = "select wmsPosition,wmsProduct,wmsDesc,wmsDesc1,wmsDesc2 from wmspositionmaptbl where id_inspection =" + str(id_inspection)
    posFullQuery = """ select distinct codePos,picPath as Wpic from inventorymaptbl 
    where id_inspection = """ + str(id_inspection) + """
     and codePos not like '';
    """


    sqlEngine = engine()
    dbConnection = sqlEngine.connect()

    dfwms = pd.read_sql(wmsQuery,    dbConnection)

    dfFullPos = pd.read_sql(posFullQuery,    dbConnection)
    dfFullPos.to_excel("testData.xlsx", sheet_name='Pos')

    dbConnection.close()

    dfRuningPos = runningPositionsRaw(id_inspection)
    # print(dfRuningPos.columns)
    dfPos1 = decodeMach(id_inspection)
    # print("dfPos1:",dfPos1.info())
    result = pd.merge(dfwms,dfFullPos,
                      left_on="wmsPosition",
                      right_on="codePos",
                      how="inner"
                      )
    result.to_excel("testDataResult.xlsx", sheet_name='result')
    # print("result:",result)
    # print(result.columns)
 #####################################

def agregates(id_inspection,reqAsile,reqLevel):
    """
    The idea in this page is to show reliable info so when running an inspection we can understand
    what is going on on real time
    :param request:
    :return: json_array

    """
    # print("reqAsile",reqAsile)
    # print("reqLevel",reqLevel)

    json_array = []

    levelFactor = querys.getLevelFactor(id_inspection)

    df = decodeMach(id_inspection, False)
    # print("carrousel df,")
    # print(df.columns)
    df = df[
        ['rack', 'wmsProduct', 'codeUnit', 'nivel_y', 'AGVpos', 'wmsPosition', 'wmsDesc', 'wmsDesc1', 'wmsDesc2',
         'match', 'Wpic', 'Ppic', 'upic']]
    df['asile'] = df['wmsPosition'].str[4:7]
    df['position'] = df['wmsPosition'].str[8:11]
    df['level'] = df['wmsPosition'].str[10:12]

    # dfx = df[df["wmsPosition"].notnull()]
    # print('dfx: ', dfx)
    # dfa = dfx["wmsPosition"].str[4:7].unique()
    # print("dfa", dfa)


    # print(df[['wmsPosition','asile','level']])
    dfnan = df.replace(r'', np.NaN)
    # print(dfnan.info())
    dfnan["ex"] = np.NaN
    dfnan["ex"]  = dfnan["match"]*1
    dfnan= dfnan.replace(1,np.NaN)
    # print(dfnan["ex"].count)

    # print('dfnan ##' *5)
    # print()


    # print(dfnan[['asile','level','wmsProduct','codeUnit','ex']])

    # PLOTING ..  BY LEVEL AND BY ASILE
    # print('Ploting by Asile...')
    if reqLevel != 'All':
        # print("asile not All:",reqAsile)
        dfnanF = dfnan[dfnan['level'] == reqLevel]
        # print(dfnanF)
    else:
        dfnanF = dfnan
    dfagg = dfnanF[['asile','wmsProduct','codeUnit','ex']].groupby(['asile'])

    # print("-dfnanF"*0,dfnanF[['asile','wmsProduct','codeUnit','ex']])
    dfCount = dfagg.count()
    # print("-dfCount:","+" * 50)
    print(dfCount)
    # print("(("*30)
    # print(dfCount)
    json_array.append(dfCount.to_json(orient='split'))
    # dfCount.plot(kind='bar',title='Pasillos y Lecturas', ylabel='Observed PA',
    #              xlabel='Asile',figsize=(14,6))
    # print('Ploting by LEVEL...')

    ### COUNTING MATCHING BY ASILE
    # print("not matching + readed and unreaded")
    dfagg = dfnanF[['asile', 'wmsPosition','codeUnit', 'ex']].groupby(['asile'])
    # print(dfagg.ex.value_counts())
    # print(dfnanF)
    dfreadedAgg = dfnanF[dfnanF.codeUnit.notnull()]
    # print(dfreadedAgg)
    dfagg = dfreadedAgg[['asile', 'wmsPosition', 'codeUnit','ex']].groupby(['asile'])
    # print("not matching"+"^^"*30)
    # print(dfagg.ex.value_counts())
    #####

    if reqAsile != 'All':
        # print("level not All",reqLevel)
        dfnanF = dfnan[dfnan['asile'] == reqAsile]
        # print(dfnanF)
    else:
        dfnanF = dfnan

    dfagg = dfnanF[['level','wmsProduct','codeUnit','ex']].groupby(['level'])


    dfCount = dfagg.count()
    json_array.append(dfCount.to_json(orient='split'))
    # dfCount.plot(kind='bar', title='Niveles y Lecturas', ylabel='Observed PA',
    #              xlabel='level')

    ## TRYING TO PLOT ALL ASILES BY EACH LEVEL
    # print('Ploting ASILES BY LEVEL...')

    dfagg = dfnanF[['asile','level','wmsProduct','codeUnit','ex']].groupby(['level','asile'])

    dfCount = dfagg.count()
    json_array.append(dfCount.to_json(orient='split'))

    # print('plotting by level XXXXXXXXXXXXXXXX')
    # print(dfnan['level'].unique())
    # print('____before for:')


    for level in dfnan['level'].unique():
        # print(level)
        dfagg = dfnanF[dfnan['level']==level]
        dfagg = dfagg[['asile', 'wmsProduct', 'codeUnit','ex']].groupby([ 'asile'])
        dfCount = dfagg.count()
        # dfCount.plot(kind='bar', title='NIVEL '+str(level)+' - Pasillos y Lecturas', ylabel='Observed PA',
        #              xlabel='Asile', figsize=(14, 6))
        json_array.append(dfCount.to_json(orient='split'))


    return json_array

def agregatesVR(id_inspection,reqAsile,reqLevel):
    """
    The idea in this page is to show reliable info so when running an inspection we can understand
    what is going on on real time
    :param request:
    :return: json_array

    """
    # print("reqAsile",reqAsile)
    # print("reqLevel",reqLevel)
    json_array = []

    levelFactor = querys.getLevelFactor(id_inspection)


    df = decodeMachPAVR(id_inspection)
    # print("carrousel df,")
    # print(df.columns)
    df = df[
        ['vRack', 'wmsProduct', 'codeUnit', 'nivel', 'pos', 'wmsPosition', 'wmsDesc', 'wmsDesc1', 'wmsdesc2',
         'match', 'picPath']]

    df['asile'] = df['wmsPosition'].str[4:7]
    df['position'] = df['wmsPosition'].str[8:11]
    df['level'] = df['wmsPosition'].str[10:12]
    # print("agregatesVR","1"*20)

    # dfx = df[df["wmsPosition"].notnull()]
    # print('dfx: ', dfx)
    # dfa = dfx["wmsPosition"].str[4:7].unique()
    # print("dfa", dfa)


    # print(df[['wmsPosition','asile','level']])
    dfnan = df.replace(r'', np.NaN)
    # print(dfnan.info())
    dfnan["ex"] = np.NaN
    dfnan["ex"]  = dfnan["match"]*1
    dfnan= dfnan.replace(1,np.NaN)
    # print(dfnan["ex"].count)

    # print('dfnan ##' *5)
    # print()


    # print(dfnan[['asile','level','wmsProduct','codeUnit','ex']])

    # PLOTING ..  BY LEVEL AND BY ASILE
    # print('Ploting by Asile...')
    if reqLevel != 'All':
        # print("asile not All:",reqAsile)
        dfnanF = dfnan[dfnan['level'] == reqLevel]
        # print(dfnanF)
    else:
        dfnanF = dfnan
    dfagg = dfnanF[['asile','wmsProduct','codeUnit','ex']].groupby(['asile'])

    # print("-dfnanF"*0,dfnanF[['asile','wmsProduct','codeUnit','ex']])
    dfCount = dfagg.count()
    # print("-dfCount:","+" * 50)
    # print(dfCount)
    # print("(("*30)
    # print(dfCount)
    json_array.append(dfCount.to_json(orient='split'))
    # dfCount.plot(kind='bar',title='Pasillos y Lecturas', ylabel='Observed PA',
    #              xlabel='Asile',figsize=(14,6))
    # print('Ploting by LEVEL...')

    ### COUNTING MATCHING BY ASILE
    # print("not matching + readed and unreaded")
    dfagg = dfnanF[['asile', 'wmsPosition','codeUnit', 'ex']].groupby(['asile'])
    # print(dfagg.ex.value_counts())
    # print(dfnanF)
    dfreadedAgg = dfnanF[dfnanF.codeUnit.notnull()]
    # print(dfreadedAgg)
    dfagg = dfreadedAgg[['asile', 'wmsPosition', 'codeUnit','ex']].groupby(['asile'])
    # print("not matching"+"^^"*30)
    # print(dfagg.ex.value_counts())
    #####

    if reqAsile != 'All':
        # print("level not All",reqLevel)
        dfnanF = dfnan[dfnan['asile'] == reqAsile]
        # print(dfnanF)
    else:
        dfnanF = dfnan

    dfagg = dfnanF[['level','wmsProduct','codeUnit','ex']].groupby(['level'])


    dfCount = dfagg.count()
    json_array.append(dfCount.to_json(orient='split'))
    # dfCount.plot(kind='bar', title='Niveles y Lecturas', ylabel='Observed PA',
    #              xlabel='level')

    ## TRYING TO PLOT ALL ASILES BY EACH LEVEL
    # print('Ploting ASILES BY LEVEL...')

    dfagg = dfnanF[['asile','level','wmsProduct','codeUnit','ex']].groupby(['level','asile'])

    dfCount = dfagg.count()
    json_array.append(dfCount.to_json(orient='split'))

    # print(dfnan['level'].unique())
    # print('____before for:')


    for level in dfnan['level'].unique():
        # print(level)
        dfagg = dfnanF[dfnan['level']==level]
        dfagg = dfagg[['asile', 'wmsProduct', 'codeUnit','ex']].groupby([ 'asile'])
        dfCount = dfagg.count()
        # dfCount.plot(kind='bar', title='NIVEL '+str(level)+' - Pasillos y Lecturas', ylabel='Observed PA',
        #              xlabel='Asile', figsize=(14, 6))
        json_array.append(dfCount.to_json(orient='split'))

    # print("agregatesVR ------END ------","*"*20)

    return json_array

def agregatesVR_noPD(id_inspection,reqAsile,reqLevel):
    """
    The idea in this page is to show reliable info so when running an inspection we can understand
    what is going on on real time
    :param request:
    :return: json_array

    """
    # print("reqAsile",reqAsile)
    # print("reqLevel",reqLevel)
    json_array = []

    levelFactor = querys.getLevelFactor(id_inspection)


    df = decodeMachVR_noPD(id_inspection)
    # print("carrousel df,")
    # print(df.columns)
    df = df[
        ['vRack', 'wmsProduct', 'codeUnit', 'nivel', 'pos', 'wmsPosition', 'wmsDesc', 'wmsDesc1', 'wmsdesc2',
         'match', 'picPath']]

    df['asile'] = df['wmsPosition'].str[4:7]
    df['position'] = df['wmsPosition'].str[8:11]
    df['level'] = df['wmsPosition'].str[10:12]
    # print("agregatesVR","1"*20)

    # dfx = df[df["wmsPosition"].notnull()]
    # print('dfx: ', dfx)
    # dfa = dfx["wmsPosition"].str[4:7].unique()
    # print("dfa", dfa)


    # print(df[['wmsPosition','asile','level']])
    dfnan = df.replace(r'', np.NaN)
    # print(dfnan.info())
    dfnan["ex"] = np.NaN
    dfnan["ex"]  = dfnan["match"]*1
    dfnan= dfnan.replace(1,np.NaN)
    # print(dfnan["ex"].count)

    # print('dfnan ##' *5)
    # print()


    # print(dfnan[['asile','level','wmsProduct','codeUnit','ex']])

    # PLOTING ..  BY LEVEL AND BY ASILE
    # print('Ploting by Asile...')
    if reqLevel != 'All':
        # print("asile not All:",reqAsile)
        dfnanF = dfnan[dfnan['level'] == reqLevel]
        # print(dfnanF)
    else:
        dfnanF = dfnan
    dfagg = dfnanF[['asile','wmsProduct','codeUnit','ex']].groupby(['asile'])

    # print("-dfnanF"*0,dfnanF[['asile','wmsProduct','codeUnit','ex']])
    dfCount = dfagg.count()
    # print("-dfCount:","+" * 50)
    # print(dfCount)
    # print("(("*30)
    # print(dfCount)
    json_array.append(dfCount.to_json(orient='split'))
    # dfCount.plot(kind='bar',title='Pasillos y Lecturas', ylabel='Observed PA',
    #              xlabel='Asile',figsize=(14,6))
    # print('Ploting by LEVEL...')

    ### COUNTING MATCHING BY ASILE
    # print("not matching + readed and unreaded")
    dfagg = dfnanF[['asile', 'wmsPosition','codeUnit', 'ex']].groupby(['asile'])
    # print(dfagg.ex.value_counts())
    # print(dfnanF)
    dfreadedAgg = dfnanF[dfnanF.codeUnit.notnull()]
    # print(dfreadedAgg)
    dfagg = dfreadedAgg[['asile', 'wmsPosition', 'codeUnit','ex']].groupby(['asile'])
    # print("not matching"+"^^"*30)
    # print(dfagg.ex.value_counts())
    #####

    if reqAsile != 'All':
        # print("level not All",reqLevel)
        dfnanF = dfnan[dfnan['asile'] == reqAsile]
        # print(dfnanF)
    else:
        dfnanF = dfnan

    dfagg = dfnanF[['level','wmsProduct','codeUnit','ex']].groupby(['level'])


    dfCount = dfagg.count()
    json_array.append(dfCount.to_json(orient='split'))
    # dfCount.plot(kind='bar', title='Niveles y Lecturas', ylabel='Observed PA',
    #              xlabel='level')

    ## TRYING TO PLOT ALL ASILES BY EACH LEVEL
    # print('Ploting ASILES BY LEVEL...')

    dfagg = dfnanF[['asile','level','wmsProduct','codeUnit','ex']].groupby(['level','asile'])

    dfCount = dfagg.count()
    json_array.append(dfCount.to_json(orient='split'))

    # print(dfnan['level'].unique())
    # print('____before for:')


    for level in dfnan['level'].unique():
        # print(level)
        dfagg = dfnanF[dfnan['level']==level]
        dfagg = dfagg[['asile', 'wmsProduct', 'codeUnit','ex']].groupby([ 'asile'])
        dfCount = dfagg.count()
        # dfCount.plot(kind='bar', title='NIVEL '+str(level)+' - Pasillos y Lecturas', ylabel='Observed PA',
        #              xlabel='Asile', figsize=(14, 6))
        json_array.append(dfCount.to_json(orient='split'))

    # print("agregatesVR ------END ------","*"*20)

    return json_array


def readAggregate(id_inspection):
    json_array = []


    df = fullDeDupR1(id_inspection)
    # print(df)
    df = df.replace(r'', np.NaN)
    df['asile'] = df['codePos'].str[4:7]
    df['position'] = df['codePos'].str[8:11]
    df['level'] = df['codePos'].str[10:12]


    # PLOTING ..  BY LEVEL AND BY ASILE
    # print('Ploting by Asile...')

    dfagg = df[['asile','codeUnit']].groupby(['asile'])
    dfCount = dfagg.count()
    # print(dfCount)
    json_array.append(dfCount.to_json(orient='split'))
    # dfCount.plot(kind='bar',title='Pasillos y Lecturas', ylabel='Observed PA',
    #              xlabel='Asile',figsize=(14,6))
    # print('Ploting by LEVEL...')

    dfagg = df[['nivel_y','codeUnit']].groupby(['nivel_y'])
    dfCount = dfagg.count()
    # print(dfCount)
    json_array.append(dfCount.to_json(orient='split'))

    # print (json_array)
    return json_array

def getRawDataByUnit(id_inspection,unit):

    query0 = "set @vector=0 ;"
    query1 = "select id_Vector into @vector from inventorymaptbl where id_inspection=" + str(
        id_inspection) + " and codeUnit like '" + unit + "' order by rack desc limit 1;"
    query3 = "select * from inventorymaptbl where id_inspection= "+str(id_inspection)+" and id_Vector>@vector-10 and id_Vector<@vector+15 order by rack desc;"

    # print(query1)
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()

    dbConnection.execute(query1)
    # dfv = pd.read_sql("select @vector", dbConnection)
    # print("dfv:",dfv)
    dfp = pd.read_sql(query3, dbConnection)

    dbConnection.close()

    return dfp[['id_Vector','rack','x','codePos','codeUnit','customCode3','nivel']]

def getWmsPosByUnit(id_inspection,unit):
    query1 = "select * from wmspositionmaptbl where id_inspection= " + str(
        id_inspection) + " and wmsProduct like '"+unit+"';"

    # print(query1)
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    # dbConnection.execute(query1)
    # dfv = pd.read_sql("select @vector", dbConnection)
    # print("dfv:",dfv)
    dfp = pd.read_sql(query1, dbConnection)
    # print("dfp"*20,dfp)
    dbConnection.close()
    return dfp

def getWmsPosByUnit(id_inspection,unit):
    query1 = "select * from wmspositionmaptbl where id_inspection= " + str(
        id_inspection) + " and wmsProduct like '"+unit+"';"

    # print(query1)
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    # dbConnection.execute(query1)
    # dfv = pd.read_sql("select @vector", dbConnection)
    # print("dfv:",dfv)
    dfp = pd.read_sql(query1, dbConnection)
    # print("dfp"*20,dfp)
    dbConnection.close()
    return dfp

def pdDF(query):
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    dfp = pd.read_sql(query, dbConnection)
    dbConnection.close()
    return dfp

###############################


def getStatus(device):
    dfQuery = "select *  from status where device like '" + str(device) + "' and status not like 'x' order by id_status desc limit 1; "
    dfVoltageQuery = "select *  from status where device like '" + str(device) + "' order by id_status desc limit 1; "
    # print('dfQuery',dfQuery)
    # print('dfVoltageQuery', dfVoltageQuery)
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    dfStatus = pd.read_sql(dfQuery, dbConnection)
    # status = dfStatus['status'][0]
    df = pd.read_sql(dfVoltageQuery, dbConnection)
    # print(df)

    voltage = df['voltages'][0]
    zero_status = df['zero'][0]
    # print("voltage: ")
    # print(voltage)
    dbConnection.close()
    # print("dfStatus:",dfStatus)

    return dfStatus,voltage,zero_status

def getDevices():
    query = "select distinct device  from status ; "

    # print('dfQuery',dfQuery)
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    dfStatus = pd.read_sql(query, dbConnection)

    dbConnection.close()


    return dfStatus


def getLastPosition(device):
    lastReadQuery = "select substring(codePos,5,6) as pos from inventorymaptbl where device like '"+str(device)+"' and codePos not like '' order by id_Vector desc limit 1;"

    lastRead = mysqlQuery(lastReadQuery).iloc[0,0]
    lastRead = "Aisle:" + lastRead[0:3] + " Pos:" + lastRead[3:6]


    return lastRead

def vBarDistances(id_device):
    distanceQuery = "select customCode3,visionBar from inventorymaptbl where device like '" + str(id_device) \
                    + "'   AND customCode3 like '%%PALLET%%' order by id_vector desc LIMIT 20;"
    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    # print(distanceQuery)
    df = pd.read_sql(distanceQuery, dbConnection)
    dbConnection.close()
    df[['a', 'state', 'dist', 'd', 'e', ]] = df['customCode3'].str.split(':', expand=True)
    df.drop(['d', 'e'], axis=1)
    df['dist'] = df['dist'].astype('int32')
    dist = df[['dist', 'visionBar']][df['state'] == "TRUE"].groupby('visionBar').agg('mean')

    return dist

def lastInspectionTime(id_device):
    last_id_inspection_query = "select id_inspection from inventorymaptbl where device like '"+\
                    str(id_device)+"' and id_inspection not like '' order by id_vector desc LIMIT 1;"

    sqlEngine = engine()
    dbConnection = sqlEngine.connect()
    # print(distanceQuery)
    df_li = pd.read_sql(last_id_inspection_query, dbConnection)
    last_id_inspection = df_li['id_inspection'][0]
    last_id_inspection =155
    start_time = "select time from inventorymaptbl where device like '" + \
                 str(id_device) + "' and id_inspection = " + str(
        last_id_inspection) + " and time not like '' order by id_vector asc LIMIT 1;"
    end_time = "select time from inventorymaptbl where device like '" \
               + str(id_device) + "' and id_inspection = " + str(
        last_id_inspection) + " and time not like '' order by id_vector desc LIMIT 1;"
    df_st = pd.read_sql(start_time, dbConnection)
    df_et = pd.read_sql(end_time, dbConnection)

    dbConnection.close()
    print ("lastInspectionTime",df_st,df_et)

    return last_id_inspection,df_st,df_et





