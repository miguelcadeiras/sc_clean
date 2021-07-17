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
    if IPAddr != '151.106.108.129' :
        # print(" here")
        mysql_alchemyDevConString = 'mysql+pymysql://webuser:Smartcubik1web@127.0.0.1/inventory'
    else:
        # print(" 2here")
        mysql_alchemyDevConString = 'mysql+pymysql://smartcubik:Smartcubik1Root!@151.106.108.129/inventory'

    sqlEngine = create_engine(mysql_alchemyDevConString)

    return sqlEngine

# mysql_alchemyDevConString = secrets.mysql_alchemyDevConString

# print(secrets.mysql_schema)



# dbConnection = sqlEngine.connect()
# df = pd.read_sql("select * from inventorymapTbl where id_inspection=27", dbConnection)
# dbConnection.close()
# print(df)

def runningPositionsRaw(id_inspection):
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
    # print(correctionFactor[5])
    df = runningPositionsRaw(id_inspection)

    # solo nos quedamos con los 6 digitos
    df['purePos'] = df['Pos'].str[4:]
    # print(df)
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
    # print(df2)
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

    levelFactor = querys.getLevelFactor(id_inspection)
    # print("LevelFactor: ->",levelFactor,type(levelFactor))
    useDeDup = querys.getUseDeDup(id_inspection)
    print("useDeDup",useDeDup)
    df2 = correctionFactor(levelFactor, id_inspection)
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

        # print("3.------------------")
        if useDeDup:
            print("usingDedup")
            for rack in df2_duplicated["rack"]:
                dfDup = df_N2[df_N2['rack'] == rack]
                # print(dfDup[["algoPos","purePos","rack",'x','codeUnit']])
                if dfDup.shape[0] == 2:
                    #       print(rack,dfDup['codePos'].str.len())
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


    dfC = pd.concat(df_N)
    # dfC = df2
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
    # ddp.to_excel("DDP.xlsx", sheet_name='Merge Data')

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
    # print('dfnan ##' *5)

    # print(dfnan[['asile','level','wmsProduct','codeUnit','match']])

    # PLOTING ..  BY LEVEL AND BY ASILE
    # print('Ploting by Asile...')
    if reqLevel != 'All':
        # print("asile not All:",reqAsile)
        dfnanF = dfnan[dfnan['level'] == reqLevel]
        # print(dfnanF)
    else:
        dfnanF = dfnan
    dfagg = dfnanF[['asile','wmsProduct','codeUnit']].groupby(['asile'])

    # print(dfagg)
    dfCount = dfagg.count()
    # print("(("*30)
    # print(dfCount)
    json_array.append(dfCount.to_json(orient='split'))
    # dfCount.plot(kind='bar',title='Pasillos y Lecturas', ylabel='Observed PA',
    #              xlabel='Asile',figsize=(14,6))
    # print('Ploting by LEVEL...')

    ### COUNTING MATCHING BY ASILE
    print("not matching + readed and unreaded")
    dfagg = dfnanF[['asile', 'wmsPosition','codeUnit', 'match']].groupby(['asile'])
    print(dfagg.match.value_counts())
    # print(dfnanF)
    dfreadedAgg = dfnanF[dfnanF.codeUnit.notnull()]
    # print(dfreadedAgg)
    dfagg = dfreadedAgg[['asile', 'wmsPosition', 'codeUnit','match']].groupby(['asile'])
    print("not matching"+"^^"*30)
    print(dfagg.match.value_counts())
    #####

    if reqAsile != 'All':
        # print("level not All",reqLevel)
        dfnanF = dfnan[dfnan['asile'] == reqAsile]
        # print(dfnanF)
    else:
        dfnanF = dfnan

    dfagg = dfnanF[['level','wmsProduct','codeUnit']].groupby(['level'])


    dfCount = dfagg.count()
    json_array.append(dfCount.to_json(orient='split'))
    # dfCount.plot(kind='bar', title='Niveles y Lecturas', ylabel='Observed PA',
    #              xlabel='level')

    ## TRYING TO PLOT ALL ASILES BY EACH LEVEL
    # print('Ploting ASILES BY LEVEL...')

    dfagg = dfnanF[['asile','level','wmsProduct','codeUnit']].groupby(['level','asile'])

    dfCount = dfagg.count()
    json_array.append(dfCount.to_json(orient='split'))

    # print('plotting by level XXXXXXXXXXXXXXXX')
    # print(dfnan['level'].unique())
    # print('____before for:')


    for level in dfnan['level'].unique():
        # print(level)
        dfagg = dfnanF[dfnan['level']==level]
        dfagg = dfagg[['asile', 'wmsProduct', 'codeUnit']].groupby([ 'asile'])
        dfCount = dfagg.count()
        # dfCount.plot(kind='bar', title='NIVEL '+str(level)+' - Pasillos y Lecturas', ylabel='Observed PA',
        #              xlabel='Asile', figsize=(14, 6))
        json_array.append(dfCount.to_json(orient='split'))


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









