import os
import sqlite_fifo
import threading
import time
from datetime import datetime, timedelta
import re
import json
import time_diff
from dotenv import load_dotenv

load_dotenv()
print(f"Sorting JSON - {datetime.now()}")

uuid_file='src/uuid.json'
db = str(os.environ.get('DB_NAME'))
json_table_name = os.environ.get('JSON_TABLE')
table_name = os.environ.get('RAW_DATA_TABLE')
node_response_table = os.environ.get('NODE_RESPONSE_TABLE')
log_to_cloud_table = os.environ.get('LOG_CLOUD_TABLE')
set_node_time_table = os.environ.get('SET_NODE_TIME_TABLE')
time_diff_table = os.environ.get('TIME_DIFF_TABLE')

flag = {'s_flag': 0, 'e_flag': 0, 'process': 0}
data_bucket = ['']
processed_data = []

stop_event = threading.Event()


def find_start_end_pairs(data):
    pattern = re.compile(r'start(.*?)end')
    return pattern.findall(data)

def process_data(flag, data_bucket, data, processed_data):
    data_bucket[0] = data_bucket[0] + data
    start_end_pairs = find_start_end_pairs(data_bucket[0])

    for pair in start_end_pairs:
        processed_data.append(pair)
        data_bucket[0] = data_bucket[0].replace(f'start{pair}end', '', 1)


def get_data(flag, data_bucket, processed_data):

    conn_raw, cursor_raw = sqlite_fifo.init_db(db, table_name)

    while not stop_event.is_set():
        try:
            row = sqlite_fifo.pop_data(cursor_raw, conn_raw, table_name)
            if row is not None:
                data = row
                process_data(flag, data_bucket, data, processed_data)

            else:

                # print("<get_data> no data available sleeping for 4 seconds")
                time.sleep(1)

        except Exception as e:
            print(f"Exception in get_data: {e}")
            time.sleep(1)

def insert_json_data(processed_data, json_db_path):
    conn_json, cursor_json = sqlite_fifo.init_db(
        db, json_table_name)
    conn_node_response, cursor_node_response = sqlite_fifo.init_db(
        db, node_response_table)
    conn_node_time, cursor_node_time = sqlite_fifo.init_db(
        db, set_node_time_table)
    conn_log_to_cloud, cursor_log_to_cloud = sqlite_fifo.init_db(
        db, log_to_cloud_table)
    conn_node_time_table, cursor_node_time_diff = sqlite_fifo.init_db(
    db, time_diff_table)
    

    while not stop_event.is_set():
        try:
            if processed_data:
                # Get the first element and remove it from the list
                current_data = processed_data.pop(0)
                print(current_data)

                # If the first 4 characters are 'json', remove them
                mac_pattern = r"([0-9a-fA-F]{2}[:]){5}[0-9a-fA-F]{2}"

                if current_data[:4] == 'json':
                    print("<insert_json_data> json data found")
                    current_data = current_data[4:]

                    # Extract the 'created_at' value using regular expressions
                    match = re.search(
                        r'"created_at"\s*:\s*"(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2})"', current_data)
                    if match:
                        print("<insert_json_data> created_at match found")
                        created_at_str = match.group(1)

                        print(created_at_str)

                        # Parse the 'created_at' string as a datetime object
                        try:
                            created_at = datetime.strptime(
                                created_at_str, "%Y-%m-%d %H:%M:%S")
                        except:
                            created_at = datetime(2000, 1, 1, 0, 0, 0)

                        print(created_at)

                        # Get the current date and time
                        current_time = datetime.now()

                        # Calculate the time difference
                        time_difference = current_time - created_at
                        print(f"time diff is {time_difference}")

                        # Check if the time difference is within 1 year
                        if (
                            time_difference <= timedelta(minutes=525600) 
                        ):
                            print("<insert_json_data> inserting")
                            mac_address = current_data[:17]
                            
                            current_data=time_diff.add_time_diff_lat_long(current_data,cursor_node_time_diff,conn_node_time_table,time_diff_table)
                            sqlite_fifo.push_data(cursor_json, conn_json,
                                                json_table_name, current_data)

                        else:
                            mac_match = re.search(mac_pattern, current_data)
                            if mac_match:
                                mac = mac_match.group()
                                print(f"mac is {mac}")
                                if (sqlite_fifo.search_string(cursor_node_time,
                                                            set_node_time_table, mac) == False):

                                    sqlite_fifo.push_data(cursor_node_time, conn_node_time,
                                                        set_node_time_table, mac)
                                    print(f"send time set command to {mac}")
                                else:

                                    print("mac already in table")

                                print("<insert_json_data> Timestamp out of range")
                                print(created_at_str)

                            print("<insert_json_data> Timestamp out of range")
                            # print created_at
                            print(created_at_str)

                elif current_data[:10] == 'configured' or current_data[:3] == 'ota':
                    sqlite_fifo.push_data(cursor_node_response, conn_node_response,
                                        node_response_table, current_data)

                    mac_address = current_data[:17]
                    message = current_data[17:]
                    time_stamp = str(datetime.now().isoformat())

                    json_data = {
                        "mac_address": mac_address,
                        "message": message,
                        "timestamp": time_stamp
                    }
                    # convert json_data to string
                    json_string = json.dumps(json_data)
                    sqlite_fifo.push_data(
                        cursor_log_to_cloud, conn_log_to_cloud, log_to_cloud_table, json_string)
                    print(
                        "<insert_json_data> node response inserted to node_response table and log_to_cloud")
                else:
                    # current_data=current_data+str(datetime.now())
                    mac_address = current_data[:17]
                    message = current_data[17:]
                    time_stamp = str(datetime.now().isoformat())
            # make a json of mac_address and message and send it
                    json_data = {
                        "mac_address": mac_address,
                        "message": message,
                        "timestamp": time_stamp
                    }
                    # convert json_data to string
                    json_string = json.dumps(json_data)
                    sqlite_fifo.push_data(
                        cursor_log_to_cloud, conn_log_to_cloud, log_to_cloud_table, json_string)
                    print("<insert_json_data> inserting to log to cloud")

            else:
                time.sleep(1)

        except Exception as e:
            print(f"Exception in insert_json_data: {e}")
            time.sleep(1)

t1 = threading.Thread(target=get_data, args=(
    flag, data_bucket, processed_data))
t2 = threading.Thread(target=insert_json_data,
                      args=(processed_data, db))

t1.start()
t2.start()

try:
    # Wait for both threads to finish (this will never happen since they run forever)
    t1.join()
    t2.join()
except KeyboardInterrupt:
    print("Stopping the program...")
    stop_event.set()
    t1.join()
    t2.join()
    print("Program stopped.")
