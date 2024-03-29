import json

import mysql.connector
import csv

import pandas as pd
from mysql.connector import errorcode,constants
from time import process_time
from django.conf import settings
import socket



mysql_schema = 'inventory'
mysql_user = 'smartcubik'
mysql_password = 'Smartcubik1Root!'
mysql_host = '151.106.108.129'

mysql_schemaDev = 'inventory'
mysql_userDev = 'webuser'
mysql_passwordDev = 'Smartcubik1web'
mysql_hostDev = 'localhost'


def connect():
    try:
        if settings.DEBUG:
            cnx = mysql.connector.connect(host=mysql_hostDev, user=mysql_userDev, password=mysql_passwordDev,
                                      database=mysql_schemaDev)
        else:
            cnx = mysql.connector.connect(host=mysql_host, user=mysql_user, password=mysql_password,
                                          database=mysql_schema)

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your user name or password Bitch")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)
    else:
        print("succes")
        cnx.close()


def openConnection():
    hostname = socket.gethostname()
    IPAddr = socket.gethostbyname(hostname)
    # print(" querys module" ,hostname,IPAddr)

    if IPAddr != '151.106.108.129' :
        cnx = mysql.connector.connect(host=mysql_hostDev, user=mysql_userDev, password=mysql_passwordDev,
                                      database=mysql_schemaDev,sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION')

        # cnx.sql_mode = 'TRADITIONAL,NO_ENGINE_SUBSTITUTION'
        # print("connection with:",mysql_hostDev,mysql_userDev, mysql_passwordDev,mysql_schemaDev, cnx.sql_mode)
    else:
        cnx = mysql.connector.connect(host=mysql_host, user=mysql_user, password=mysql_password,
                                      database=mysql_schema,sql_mode='STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION')
        # cnx.sql_mode = 'TRADITIONAL,NO_ENGINE_SUBSTITUTION'
        # print("connection with:", mysql_host, mysql_user, mysql_password, mysql_schema, cnx.sql_mode)

    cnx.set_charset_collation(charset='utf8mb4', collation='utf8mb4_0900_ai_ci')
    cursor = cnx.cursor()
    # cursor.execute("SET sql_mode= 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION'; SET GLOBAL sql_mode = 'STRICT_TRANS_TABLES,NO_ENGINE_SUBSTITUTION';")
    # print("sqlmode_excecuted" , cnx.sql_mode)


    return cnx,cursor


def mysqlQuery(query, *kargs):
    """

    :param query:
    :param kargs: True or False, multi Results parameter.
    :return:
    """
    # print(kargs)
    result = 'none'
    field_names = []
    try:
        cnx,cursor = openConnection()
        # if settings.DEBUG:
        #     cnx = mysql.connector.connect(host=mysql_hostDev, user=mysql_userDev, password=mysql_passwordDev,
        #                               database=mysql_schemaDev)
        # else:
        #     cnx = mysql.connector.connect(host=mysql_host, user=mysql_user, password=mysql_password,
        #                                   database=mysql_schema)

        cnx.set_charset_collation(charset='utf8mb4', collation='utf8mb4_0900_ai_ci')
        cursor = cnx.cursor()
        if len(kargs) > 0:

            result = cursor.execute(query, multi=kargs)
            # print(result)
            results = []
            field_names = []
            for r in result:
                results.append(r.fetchall())
                if r.description is not None:
                  field_names.append( [i[0] for i in r.description])
                else:
                  field_names.append([])

            cursor.close()
            cnx.close()
            # print(field_names)
            return results,field_names
        else:
            cursor.execute(query)
            results = cursor.fetchall()
            num_fields = len(cursor.description)
            field_names = [i[0] for i in cursor.description]
            # print(query)
            cnx.close()
            return results, field_names



    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)
            return 'error'
    else:
        
        return result


def execute(query):
    try:
        cnx, cursor = openConnection()
        # if settings.DEBUG:
        #     cnx = mysql.connector.connect(host=mysql_hostDev, user=mysql_userDev, password=mysql_passwordDev,
        #                                   database=mysql_schemaDev)
        # else:
        #     cnx = mysql.connector.connect(host=mysql_host, user=mysql_user, password=mysql_password,
        #                                   database=mysql_schema)
        #
        # cnx.set_charset_collation(charset='utf8mb4', collation='utf8mb4_0900_ai_ci')
        # cursor = cnx.cursor()
        cursor.execute(query)
        cnx.commit()
        cursor.close()
        cnx.close()

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)
            return 'error'
    return True


def executeMulti(query):
    try:
        cnx, cursor = openConnection()
        # if settings.DEBUG:
        #     cnx = mysql.connector.connect(host=mysql_hostDev, user=mysql_userDev, password=mysql_passwordDev,
        #                                   database=mysql_schemaDev)
        # else:
        #     cnx = mysql.connector.connect(host=mysql_host, user=mysql_user, password=mysql_password,
        #                                   database=mysql_schema)
        # cnx.set_charset_collation(charset='utf8mb4', collation='utf8mb4_0900_ai_ci')
        # cursor = cnx.cursor()
        cursor.execute(query,multi=True)
        cnx.commit()
        cursor.close()
        cnx.close()

    except mysql.connector.Error as err:
        if err.errno == errorcode.ER_ACCESS_DENIED_ERROR:
            print("Something is wrong with your user name or password")
        elif err.errno == errorcode.ER_BAD_DB_ERROR:
            print("Database does not exist")
        else:
            print(err)
            return 'error'
    return True


def getClientID(clientName):
    query = "SELECT id_client FROM clienttbl where clientName like '" + str(clientName) + "';"
    result = mysqlQuery(query)
    # print(result)
    return result



def getWarehouses(id_client):
    query = 'SELECT warehousestbl.name,address,city,country,id_warehouse FROM warehousestbl where id_client=' + str(
        id_client) + ';'
    result = mysqlQuery(query)
    # print(query)
    return result


def getWarehouseName(id_inspection):
    query = 'SELECT warehousestbl.name,address,city,country FROM warehousestbl inner join inspectiontbl on inspectiontbl.id_warehouse = warehousestbl.id_warehouse where id_inspection=' + str(
        id_inspection) + ';'
    result = mysqlQuery(query)
    # print(query)
    # print(result)
    return result


def getInspections(id_warehouse):
    query = 'SELECT id_inspection,description,inspectionDate FROM inspectiontbl where id_warehouse=' + str(
        id_warehouse) + ' order by id_inspection desc;'
    result = mysqlQuery(query)
    # print(query)
    return result



def getInspectionData(id_inspection):
    query = 'SELECT description,inspectionDate FROM inspectiontbl where id_inspection=' + str(
        id_inspection) + ';'
    result = mysqlQuery(query)
    # print(query)
    # print(result)
    return result

def getLevelFactor(id_inspection):
    query = 'SELECT levelFactor FROM inspectiontbl where id_inspection=' + str(
        id_inspection) + ';'
    result = mysqlQuery(query)
    # print("%"*30)
    # print( "result:",result)
    rt = result[0][0][0]

    rt = rt[1:-1]
    rtList = rt.split(",")
    rtDict = {}
    for item in rtList:
        vals = item.split(":")


        rtDict[int(vals[0])] = float(vals[1])

    # print("rt",rtDict,type(rt))

    return rtDict


def getUseDeDup(id_inspection):
    query = 'SELECT useDeDup FROM inspectiontbl where id_inspection=' + str(
        id_inspection) + ';'
    result = mysqlQuery(query)
    # print(query)
    rt = result[0][0][0]
    if rt == 1:
        rt = True
    else:
        rt = False

    return rt

def getRunningPositions(*args):
    id_inspection = 0
    query = 'call runningpositions();'
    if len(args) >= 0:
        offset = str(args[0])
        limit = str(args[1])
        id_inspection = str(args[2])

        if limit == 0:
            limit = mysqlQuery('select count(distinct(codePos)) from inventorymaptbl where id_inspection='+str(id_inspection))[0][0][0]


        query = 'CALL runningpositions(' + id_inspection + ',' + offset + ',' + limit + ');'

    result = mysqlQuery(query, True)

    # print(result)
    return result


def getRunningPositionsCenco(id_inspection,id_asile,id_N,id_pos,offset,qty):
    # PROCEDURE REQUIEREMENTS MYSQL
    # PROCEDURE `runningPositionsCenco`(IN idInsp INT, in idAsile varchar(10), IN idN varchar(10),in idPos varchar(20), IN offset int, in QTY int)
    # print("input Parameters","asile", id_asile,"nivel", id_N,"pos", id_pos)
    idAsile = "'%%'" if id_asile.lower() == 'all' else "'%"+str(id_asile)+"%'"
    idN = "'%%'" if id_N.lower() == 'all' else"'%"+str(id_N)+"%'"
    idPos = "'%%'" if id_pos.lower() == 'all' else "'%"+str(id_pos)+"%'"
    # print("query parameters","asile",idAsile,"nivel",idN,"pos",idPos)
    if qty == 0:
       qty = mysqlQuery('select count(distinct(codePos)) from inventorymaptbl where id_inspection='+str(id_inspection))[0][0][0]

    query = 'CALL runningpositionsCencoFull (' + id_inspection + ',' + idAsile+ ',' +idN+ ',' +idPos+ ',' + str(offset) + ',' + str(qty) + ');'
    print("query",query)
    result = mysqlQuery(query, True)

    # print(result)
    return result


def getMatching(id_inspection,*kargs):
    asile = ''
    nivel = ''
    if len(kargs)==2:
        asile = kargs[0]
        nivel = kargs[1]

    queryFilter = """
    set @id_inspection = """+str(id_inspection)+ """, @asile='%"""+str(asile)+ """%',@nivel='%"""+str(nivel)+ """%';
    with filteredWmsPositionMapTbl as (select * from wmspositionmaptbl where id_inspection=@id_inspection)

SELECT verified as v,rack as R,wmsposition,pos,wmsproduct,CASE WHEN units IS NULL then '' else units end as unit,wmsDesc as C,wmsDesc1,wmsDesc2 as Bultos,exported as E,case when wmsProduct=units then 0 else picPath end as 'check' from filteredWmsPositionMapTbl 
left join (
select distinct positions.pos,positions.rack,positions.palletType,units,unit.nivel,camera,picPath,verified,exported from (
		Select distinct substring(codePos,1,14) AS pos,rack, CASE when LENGTH(codePos)>12 then substring(codePos,11,2) else '__' end as palletType ,nivel,picPath	from inventorymaptbl 
        where 
			codePos not like '' AND
			codePos  like 'UBG1%' AND
            codePos not like '%XX%' AND
            substring(codePos,11,2) not like '01' and
            length(codePos)>=12 and   

            id_inspection=@id_inspection
             group by pos
		order by rack,nivel,codePos
        
        ) as positions
        left Join (
			        Select distinct codeUnit AS units,nivel,camera ,rack,exported,verified	from inventorymaptbl 
						where 
								codePos like ''
								and customCode1 like ''
								and customCode2 like ''
								and customCode3 like ''
								and id_inspection=@id_inspection
						group by codeUnit
						order by rack,nivel,camera) as unit
		on positions.rack=unit.rack and positions.nivel=unit.nivel
        
        order by pos) as readedPositions
        on filteredWmsPositionMapTbl.wmsPosition=readedPositions.pos
        where id_inspection=@id_inspection and rack IS NOT NULL
        
        and substring(wmsposition,5,3) like @asile 
        and substring(wmsposition,11,2) like @nivel
        group by wmsposition
        ;
    """
    query = """

set @id_inspection = """+str(id_inspection)+""";
with filteredWmsPositionMapTbl as (select * from wmspositionmaptbl where id_inspection=@id_inspection)
SELECT verified as v,rack as R,wmsposition,pos,wmsproduct,CASE WHEN units IS NULL then '' else units end as unit,wmsDesc as C,wmsDesc1,wmsDesc2 as Bultos,exported as E,case when wmsProduct=units then 0 else picPath end as 'check' from filteredWmsPositionMapTbl
left join (
select distinct positions.pos,positions.rack,positions.palletType,units,unit.nivel,camera,picPath,verified,exported from (
		Select distinct substring(codePos,1,14) AS pos,rack, CASE when LENGTH(codePos)>12 then substring(codePos,11,2) else '__' end as palletType ,nivel,picPath	from inventorymaptbl 
        where 
			codePos not like '' AND
			codePos  like 'UBG1%' AND
            codePos not like '%XX%' AND
            substring(codePos,11,2) not like '01' and
            length(codePos)>=12 and   

            id_inspection=@id_inspection
             group by pos
		order by rack,nivel,codePos
        
        ) as positions
        left Join (
			        Select distinct codeUnit AS units,nivel,camera ,rack,exported,verified	from inventorymaptbl 
						where 
								codePos like ''
								and customCode1 like ''
								and customCode2 like ''
								and customCode3 like ''
								and id_inspection=@id_inspection
						group by codeUnit
						order by rack,nivel,camera) as unit
		on positions.rack=unit.rack and positions.nivel=unit.nivel
        
        order by pos) as readedPositions
        on filteredWmsPositionMapTbl.wmsPosition=readedPositions.pos
        where id_inspection=@id_inspection and rack IS NOT NULL
        group by wmsposition
        ;
    """
    # print(query)
    if len(kargs) == 2:

        print(queryFilter)
        result = mysqlQuery(queryFilter, True)

    else:
        result = mysqlQuery(query, True)
        # print("this query")
        print(query)
        # print("result",result)

    # print("res 1: ",result[1])
    # print("res 0: ",result[0])
    return result
# def getLevels():
#   query = 'select * from levels;'
#   levels = mysqlQuery(query)
#   # print(levels[0])
#   return levels[0]


def getLevels(id_inspection):
    query = "call inventory.levels(" + str(id_inspection) + ");"
    # print("query",query)

    levels = mysqlQuery(query, True)
    # print("getLevels:", levels)
    return levels[0]


def unitsByLevel(level):
    query = "select * from positions_by_level;"
    # print(query)
    result = mysqlQuery(query)
    # print(result)
    return result


def unitsByLevel(level, id_inspection):
    query = "select * from positions_by_level where id_inspection=" + str(id_inspection) + ";"
    # print(query)
    result = mysqlQuery(query)
    # print(result)
    return result


def levelOcupation(level):
    # print(type(level), level)
    query = """   select
  count(distinct(position))
  from positions_by_level where
  `nivel`
  like
  '""" + level + """';"""
    query1 = """select
  count(distinct(unit))
  from positions_by_level where
  `nivel`
  like
  '""" + level + """';
  """
    result = mysqlQuery(query)[0][0][0]
    result1 = mysqlQuery(query1)[0][0][0]

    # print(result)
    return result, result1


def levelOcupation(level, id_inspection):
    # print(type(level), level)
    query = """   select
  count(distinct(position))
  from positions_by_level where
  `nivel`
  like
  '""" + level + """';"""
    query1 = """select
  count(distinct(unit))
  from positions_by_level where
  `nivel`
  like
  '""" + level + """' where id_inspection=""" + str(id_inspection) + """
  
  ;
  """
    result = mysqlQuery(query)[0][0][0]
    result1 = mysqlQuery(query1)[0][0][0]

    # print(result)
    return result, result1


def importData(myfile,id_inspection):
    # try:
    # Start the stopwatch / counter
    t1_start = process_time()

    with open(myfile, 'r') as csv_file:
            reader = csv.reader(csv_file, delimiter=',', quotechar='|')
            for index,row in enumerate(reader):
                if index == 0:
                    print(row)
                else:
                    query = "insert into wmspositionmaptbl (wmsposition,wmsproduct,wmsdesc,wmsdesc1,id_inspection) values('"+row[0]+"','"+row[1]+"','"+row[2]+"','"+row[3]+"',"+str(id_inspection)+");"
                    # print("query", query)
                    if index == 1:

                        print("query",query)

                    # mysqlQuery(query, False)
                    execute(query)

            print("import Process Finished")

    # Stop the stopwatch / counter
    t1_stop = process_time()
    print("Elapsed time during the whole program in seconds:",
          t1_stop - t1_start)
    return True


def importDataBulk(myfile,id_inspection):
    # try:
    # Start the stopwatch / counter
    t1_start = process_time()

    df_read=pd.read_csv(myfile)
    print(df_read)

    with open(myfile, 'r',encoding='utf-8',errors='surrogateescape') as csv_file:
            header = "insert into wmspositionmaptbl (wmsposition,wmsproduct,wmsdesc,wmsdesc1,wmsdesc2,id_inspection) values"
            query= header
            reader = csv.reader(csv_file, delimiter=',', quotechar='|')

            rowCount = 0
            r=0
            # print("here")
            # for index,row in enumerate(reader):
            for index, row in df_read.iterrows():
                    # print("index:",index)
                    # print("row",row)
                    print("----------",row[0])
                # if index == 0:
                #     next
                #     #print(row)
                # else:
                    if "'" in str(row[3]) :
                        row[3]=str(row[3]).replace("'"," ")
                    query += "('"+str(row[0])+"','"+str(row[1])+"','"+str(row[2])+"','"+str(row[3])+"','"+str(row[4])+"',"+str(id_inspection)+"),"
                    # print("query", query)
                    # if index == 1:
                    #     # print("query",query)
                    #     next

                    if rowCount > 5000:
                        # print("ROWWW:",r)
                        # print("query", query[:-1])
                        execute(query[:-1])
                        # print("executed")
                        query = header
                        rowCount = 0
                    rowCount += 1
                    r +=1

            # print("query", query)
            if len(query) > len(header):
                execute(query[:-1])

            print("import Process Finished")

    # Stop the stopwatch / counter
    t1_stop = process_time()
    print("Elapsed time during the whole program in seconds:",
          t1_stop - t1_start)
    return True


def deleteData(id_inspection):
    try:
        query = "DELETE  FROM wmspositionmaptbl where id_inspection ="+str(id_inspection)+";"
        execute(query)
        return True
    except:
        print("someError")
        return False


def getWMSData(id_inspection):
    query = "select wmsposition,wmsproduct,wmsDesc,wmsDesc1,wmsDesc2 from wmspositionmaptbl where id_inspection = "+str(id_inspection)+" limit 1000;"
    return mysqlQuery(query,False)


def deleteWMSData(id_inspection):
    query = "delete form wmspositiontable where id_inspection="+str(id_inspection)
    mysqlQuery(query, False)
    return

# def getLevelFactor(id_inspection):
#     """
#     for a given inspection returns levelFactor correction in case the mast wasn't correctly align when doing
#     the inspection
#     :param id_inspection:
#     :return:
#     """
#     levelFactorQuery = "select levelFactor from inspectiontbl where id_inspection = "+ str(id_inspection)
#
#     return mysqlQuery(levelFactorQuery,False)