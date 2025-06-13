import os
import re
from datetime import datetime
import json 
import sqlite_fifo
from dotenv import load_dotenv

load_dotenv()

uuid_file='src/uuid.json'
db = str(os.environ.get('DB_NAME'))

'''sqlite_fifo.search_string(cursor_node_time,set_node_time_table, mac)'''    
        
def get_solution_name(uuid_file, mac_address):
    with open(uuid_file, 'r') as f:
        uuid_map = json.load(f)

    solution_name = uuid_map.get(mac_address, {}).get("solution_name")

    if solution_name:
        return solution_name
    else:
        return ""

#function to get keys of latitude,longitude and time difference   
def get_keys(file_name,mac_address):
    with open(file_name, 'r') as f:
        uuid_map = json.load(f)
    key_lat=uuid_map.get(mac_address, {}).get("key_lat")
    key_long=uuid_map.get(mac_address, {}).get("key_long")
    key_time_diff=uuid_map.get(mac_address, {}).get("key_time_diff")
    print(key_lat,key_long,key_time_diff)
    if not key_lat:
        key_lat=""
    if not key_long:
        key_long=""
    if not key_time_diff:
        key_time_diff=""

    return str(key_lat),str(key_long),str(key_time_diff)     


def get_lat_long(file_name,mac_address):
    with open(file_name, 'r') as f:
        uuid_map = json.load(f)
    lat=uuid_map.get(mac_address, {}).get("lat")
    long=uuid_map.get(mac_address, {}).get("long")

    if not lat:
        lat=""
    if not long:
        long=""


    return str(lat),str(long)     

def extract_date_time_from_string(input_string):
    pattern = r'(\d{4}-\d{1,2}-\d{1,2} \d{1,2}:\d{1,2}:\d{1,2})'
    match = re.search(pattern, input_string)
    if match:
        date_time_str = match.group(1)
        return date_time_str
    else:
        return None

def extract_mac_address_from_string(input_string):
    pattern = r'(\b(?:[0-9a-fA-F]{2}:){5}[0-9a-fA-F]{2}\b)'
    match = re.search(pattern, input_string)
    if match:
        mac_address = match.group(1)
        return mac_address
    else:
        return None

def extract_sensor_id_from_string(input_string):
    pattern = r'SensorID:(\d+)'
    match = re.search(pattern, input_string)
    if match:
        sensor_id = int(match.group(1))
        return sensor_id
    else:
        return 0

def get_previous_time(mac_address,current_time,cursor,conn,table):
    #try to get the previous time from the database and 
    if sqlite_fifo.search_string(cursor,table,mac_address)==False:
        return None

    else:
        previous_time=sqlite_fifo.search_substring(cursor,table,mac_address)
        print(f"previous time is {previous_time}")
        previous_time=  extract_date_time_from_string(previous_time)#previous_time[17:]
        print(f"previous time is {previous_time}")
        previous_time=datetime.strptime(previous_time, "%Y-%m-%d %H:%M:%S")
        sqlite_fifo.update_string(conn,table,mac_address,mac_address+" "+str(current_time))

        return previous_time


def get_time_difference(search_id, current_time,cursor,conn,table):
    '''connect to the databse , calculate and return the time_difference '''
    # print(f"current hour is {current_time.hour},day is {current_time.day}")
    ''' calculate time difference in minutes '''
    previous_time=get_previous_time(str(search_id),current_time,cursor,conn,table)
    if previous_time is not None:
        time_difference = current_time - previous_time
        #if current time is smaller than previous time then return ER03
        if time_difference.total_seconds()<0:
            return "ER03"
        else:
            #sqlite_fifo.update_string(conn,table,mac_address,mac_address+str(current_time))
           return "{:.2f}".format(time_difference.total_seconds() / 60)

    else:
        sqlite_fifo.push_data(cursor,conn,table,search_id+str(current_time)) # will have to write some logic to push and extract this data
        return str(5)


def add_time_diff_lat_long(post_data,cursor,conn,table):
    '''acces the databse and get the last updated time here and calculate the time difference '''
    pattern = r'"created_at":"(.*?)"'
    matches = re.findall(pattern, post_data)
    if matches:
        datetime_str =extract_date_time_from_string(post_data) #matches[0]
        mac_address=extract_mac_address_from_string(post_data)
        sensor_id="SensorID:"+str(extract_sensor_id_from_string(post_data))
        search_id=mac_address+sensor_id+"X"

        current_time = datetime.strptime(datetime_str, "%Y-%m-%d %H:%M:%S")
        time_diff = get_time_difference(search_id, current_time,cursor,conn,table)
        '''add time diff before created_at'''

        solution_name = get_solution_name(uuid_file,mac_address)
      
        key_lat, key_long ,key_time_diff= get_keys(uuid_file,mac_address)
        lat,long_=get_lat_long(uuid_file,mac_address)
        sub_string_time_diff = "\""+solution_name + \
            key_time_diff+"\":"+time_diff+","
        sub_string_lat = "\""+solution_name+key_lat+"\":"+lat+","
        sub_string_long = "\""+solution_name+key_long+"\":"+long_+","
        created_at_index = post_data.find('created_at')

        post_data = post_data[:created_at_index-1]+sub_string_time_diff + \
            sub_string_lat+sub_string_long+post_data[created_at_index-1:]

        return post_data

    else:
        return None

if __name__=="__main__":
    #demo to check if functions are working properly 
    #post_data = '78:21:84:e2:f6:94"O142":14.0,"O150":14.0,"O144":14.0,"created_at":"2023-07-3 12:16:50"SensorID:0'
    #post_data='78:21:84:e0:ee:bc"E01":100.00,"E02":100.00,"E03":100.00,"E04":100.00,"E05":100.00,"E06":100.00,"E07":100.00,"E08":100.00,"E09":100.00,"E10":100.00,"E11":200.00,"E12":200.00,"E13":200.00,"E14":200.00,"E15":200.00,"E16":200.00,"E17":200.00,"E18":200.00,"E19":200.00,"E20":200.00,"E21":300.00,"E22":300.00,"E23":300.00,"E24":300.00,"E25":300.00,"E26":300.00,"E27":300.00,"E28":300.00,"E29":300.00,"E30":300.00,"E31":400.00,"E32":400.00,"E33":400.00,"E34":400.00,"E35":400.00,"E36":400.00,"E37":400.00,"E38":"ER04","E39":"ER04","E40":"ER04","created_at":"2023-08-07 16:09:39"SensorID:400'
    time_diff_table = "time_diff"
    conn_node_time_table, cursor_node_time_diff = sqlite_fifo.init_db(
    db, time_diff_table)
    lat="14"
    long_="15"
    #print(add_time_diff_lat_long(post_data,cursor_node_time_diff,conn_node_time_table,time_diff_table,lat,long_))
  
