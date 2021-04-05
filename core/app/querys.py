import mysql.connector
from mysql.connector import errorcode


def connect():
    try:

        cnx = mysql.connector.connect(user='root', password='Smartcubik1',
                                      database='inventory')
        cnx.set_charset_collation(charset='none', collation='none')

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


def mysqlQuery(query, *kargs):
    # print(kargs)
    mysql_schema = 'inventory'
    mysql_user = 'webuser'
    mysql_password = 'Smartcubik1web'
    result = 'none'
    field_names = []
    try:
        cnx = mysql.connector.connect(host='localhost', user=mysql_user, password=mysql_password,
                                      database=mysql_schema)
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


            # print(field_names)
            return results,field_names
        else:
            cursor.execute(query)
            results = cursor.fetchall()
            num_fields = len(cursor.description)
            field_names = [i[0] for i in cursor.description]
            # print(query)
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
        cnx.close()


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
    query = 'SELECT id_inspection,description,inspectionDate FROM inspectionTbl where id_warehouse=' + str(
        id_warehouse) + ' order by id_inspection desc;'
    result = mysqlQuery(query)
    # print(query)
    return result


def getInspectionData(id_inspection):
    query = 'SELECT description,inspectionDate FROM inspectionTbl where id_inspection=' + str(
        id_inspection) + ';'
    result = mysqlQuery(query)
    # print(query)
    # print(result)
    return result


def getRunningPositions(*args):
    id_inspection = 0
    query = 'call runningpositions();'
    if len(args) >= 0:
        offset = str(args[0])
        limit = str(args[1])
        if limit == 0:
            limit = 65000

        id_inspection = str(args[2])
        query = 'CALL runningpositions(' + id_inspection + ',' + offset + ',' + limit + ');'

    result = mysqlQuery(query, True)

    # print(result)
    return result

def getMatching(id_inspection):
    query = """
    -- ####################################################################  
 --   macheo entre teorico y leido
-- #################################################################### 
SELECT rack,wmsposition,pos,wmsproduct,case when isnull(units) then '' else units end as readedUnit,wmsDesc,picPath from wmspositionmaptbl 
left join (
select distinct positions.pos,positions.rack,positions.palletType,units,unit.nivel,camera,picPath from (
		Select distinct substring(codePos,1,12) AS pos,rack, CASE when LENGTH(codePos)>12 then substring(codePos,11,2) else '__' end as palletType ,nivel,picPath	from inventorymaptbl 
        where 
			codePos not like '' AND
            codePos not like '%XX%' AND
            substring(codePos,11,2) not like '01' and
            length(codePos)>=10 and   
            # length(codePos)<14 and
            id_inspection="""+str(id_inspection)+""" 
		order by rack,nivel,codePos
        
        ) as positions
        left Join (
			        Select distinct codeUnit AS units,nivel,camera ,rack	from inventorymaptbl 
						where 
								codePos like ''
								and customCode1 like ''
								and customCode2 like ''
								and customCode3 like ''
								and id_inspection=30 
						order by rack,nivel,camera) as unit
		on positions.rack=unit.rack and positions.nivel=unit.nivel
        
        order by pos) as readedPositions
        on wmspositionmaptbl.wmsPosition=readedPositions.pos
        where id_inspection="""+str(id_inspection)+""" ;

    """
    # print(query)
    result = mysqlQuery(query, False)

    # print(result)
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


def insertDATA(fileName):
    return True

def getWMSData(id_inspection):
    query = "select wmsposition,wmsproduct,wmsDesc,wmsDesc1 from wmspositionmaptbl where id_inspection = "+str(id_inspection)
    return mysqlQuery(query,False)

def deleteWMSData(id_inspection):
    query = "delete form wmspositiontable where id_inspection="+str(id_inspection)
    mysqlQuery(query, False)
    return