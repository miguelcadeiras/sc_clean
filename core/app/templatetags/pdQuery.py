import pandas as pd
import mysql
import mysql.connector as sql
import pymysql
from sqlalchemy import create_engine
import secrets
import openpyxl

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
mysql_alchemyDevConString =  'mysql+pymysql://webuser:Smartcubik1web@127.0.0.1/inventory'

# print(secrets.mysql_schema)
sqlEngine = create_engine(mysql_alchemyDevConString)

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
    codePos not like 'UBG0%%'
    group by rack"""
    unitsQuery = """ with fullRack as(
     select distinct rack from inventorymaptbl where id_inspection ="""+str(id_inspection)+"""
      )
      select fullRack.rack,x,codeUnit,nivel,picpath as upic from fullRack left Join (
      select distinct(codeUnit),rack,x,nivel,picpath from inventorymapTbl where id_inspection = """+str(id_inspection)+""") as units
      on fullRack.rack=units.rack 
      where codeunit not like ''
    	group by codeUnit
    """
    dbConnection = sqlEngine.connect()
    dfUnits = pd.read_sql(unitsQuery, dbConnection)
    dfPos = pd.read_sql(posQuery, dbConnection)

    dbConnection.close()

    result = pd.merge(dfPos,
                      dfUnits,
                      on="rack",
                      how="outer"
                      )
    return result


def machingPositionsRaw(id_inspection):
    """
    if wmsData is pressent then returns matching positions without any
    correction or algorithm, just what we reead. No AI applied.
    :param id_inspection:
    :return:
    """
    rp = runningPositionsRaw(id_inspection)
    dbConnection = sqlEngine.connect()
    dfwms = pd.read_sql(
        "select wmsPosition,wmsProduct,wmsDesc,wmsDesc1,wmsdesc2 from wmspositionMapTbl where id_inspection ="+str(id_inspection),
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

    values = []
    modified = 0
    cfM = 0
    # print(values)
    for count, r in enumerate(df["purePos"]):
        purePos = float(r)

        if count == 0:
            # In [2]: '%03.f'%5
            # Out[2]: '005'

            values.append('%06.f' % purePos)
        else:
            x = df["x"][count]
            #         print(df["nivel_x"][count],x)
            if pd.isna(df["nivel_y"][count]):
                cf = 0
            else:
                cf = correctionFactor[float(df["nivel_y"][count])]

            #         print(x,cf,int(df["nivel_y"][count]))
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
    dbConnection = sqlEngine.connect()
    dfwms = pd.read_sql(
        "select wmsPosition,wmsProduct,wmsDesc,wmsDesc1,wmsdesc2 from wmspositionMapTbl where id_inspection =" + str(
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

    if x0 <= 1.5:
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


def fullDeDup(id_inspection,levelfactor):
    """
    :param id_inspection:
    :param mid: middle of the rack where it should change
    :param th: middle threshold
    :param levelfactor: dictionary for correction factor{level:cm,...,level_n:cm}
    :return: dataFrame
    """

    df2 = correctionFactor(levelfactor, id_inspection)
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
                        df.at[index, 'algoPos'] = newPos
                        # print(newPos, pa, oldPos, rack, dfDup['codeUnit'].values[0], dfDup['x'].values[0])
                    except:
                        pass

    print("<<<>>>>>Deduplication Completed Successfully<<<<>>>>>>")

    return pd.concat(df_N)


def testFullDeDup(id_inspection,mid,th,levelfactor,rack):
    """
    :param id_inspection:
    :param mid: middle of the rack where it should change
    :param th: middle threshold
    :param levelfactor: dictionary for correction factor{level:cm,...,level_n:cm}
    :param rack: list of rack you want to check
    :return: dataFrame
    """

    df2 = correctionFactor(levelfactor, id_inspection)
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
            print(dfDup[["algoPos","purePos","rack",'x','codeUnit']])


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


def decodeMach(id_inspection,levelfactor={2:0,3:0,4:0,5:0},export_to_excel=False):
    dfBeforeDeDup = correctionFactor(levelFactor, id_inspection)

    ddp = fullDeDup(id_inspection, levelFactor)

    dbConnection = sqlEngine.connect()
    dfwms = pd.read_sql(
        "select wmsPosition,wmsProduct,wmsDesc,wmsDesc1,wmsdesc2 from wmspositionMapTbl where id_inspection =" + str(
            id_inspection),
        dbConnection)
    dbConnection.close()

    resMergeWms = pd.merge(ddp, dfwms, left_on="codeUnit", right_on="wmsProduct", how="outer")

    # print(resMergeWms)
    if export_to_excel:
        resMergeWms.to_excel("full_join_algo_dedup_r2.xlsx", sheet_name='Merge Data')

    return resMergeWms


def pasilloNivel(id_inspection,levelFactor,pasillo,nivel):
    df = decodeMach(id_inspection, levelFactor, False)
    pas = '%03.f' % pasillo
    dfPasNiv = df[
        df['wmsPosition'].str[4:7].str.contains(pas, na=False) & df['wmsPosition'].str[11:12].str.contains(str(nivel),
                                                                                                             na=False)]

    return dfPasNiv


# print(testFullDeDup(27,1.5,0.1,{2:0,3:0,4:0.2,5:0.3},681))

# print(fullDeDup(27,1.5,0.3,{2:0,3:0,4:0.2,5:0.3}))

# ----------------------
# ---------------------


id_inspection = 27
levelFactor = {2:0,3:0,4:0.2,5:0.3}

# dfBeforeDeDup = correctionFactor(levelFactor,id_inspection)
#
#
# ddp = fullDeDup(id_inspection,1.5,0.2,levelFactor)
#
# dbConnection = sqlEngine.connect()
# dfwms = pd.read_sql(
#     "select wmsPosition,wmsProduct,wmsDesc,wmsDesc1,wmsdesc2 from wmspositionMapTbl where id_inspection =" + str(
#         id_inspection),
#     dbConnection)
# dbConnection.close()
#
# resMergeWms = pd.merge(ddp, dfwms, left_on="codeUnit", right_on="wmsProduct", how="outer")
#
# # print(resMergeWms)
# resMergeWms.to_excel("full_join_algo_dedup_r2.xlsx",sheet_name='Merge Data')
# ------------------------------
# ----------------------------

df = decodeMach(27, {2:0,3:0,4:0,5:0}, False)

print("------")
# SOLO PASILLOS
# print(df['wmsPosition'].str[4:7])
# print #SOLO POSICION
# print(df['wmsPosition'].str[8:10])
# print SOLO NIVEL
# print(df['wmsPosition'].str[11:12])

# print(df[df['wmsPosition'].str[4:7].str.contains("002", na=False)])
# print(df[df['wmsPosition'].str[11:12].str.contains("2",na=False)])

dfPasNiv = df[df['wmsPosition'].str[4:7].str.contains("002", na=False) & df['wmsPosition'].str[11:12].str.contains("2",na=False)]

dfPasNiv.info()
dfPasNiv.shape



# df = df[df['nivel_y']==2 and df['wmsPositon'].str.contains( "003")]

# print(df)

# beforeDeDupMerge = pd.merge(dfBeforeDeDup,dfwms, left_on="codeUnit", right_on="wmsProduct", how="outer")
# beforeDeDupMerge.to_excel("full_join_before-algo_dedup_r2.xlsx",sheet_name='Merge Data')





