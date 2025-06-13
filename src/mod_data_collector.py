import yaml
import minimalmodbus
import struct
import psutil
import sqlite_fifo
import subprocess
import datetime
import time
import serial
from serial.rs485 import RS485, RS485Settings
import serial.tools.list_ports
#import board
#import adafruit_dht
import Adafruit_DHT
import re
import os
import math
from datetime import datetime, timedelta
from dotenv import load_dotenv

#TAG for troubleshooting --> where the error orginated. 
tag ="[mod_data_collector.py]"

load_dotenv()
print(f"{tag} : Started Data Collection Modbus - {datetime.now()}")

pisystem = str(os.environ.get('PI_SYSTEM'))
reading_intervl=int(os.environ.get('DATA_INTERVAL'))
db = str(os.environ.get('DB_NAME'))
table_name = os.environ.get('RAW_DATA_TABLE')

# Port for RS485
PORT_RS485 = '/dev/ttyAMA1'

# Endianess of the register
BYTEORDER_BIG: int = 0  # Big-endian ABCD
BYTEORDER_LITTLE: int = 1  # Little-endian DCBA
BYTEORDER_BIG_SWAP: int = 2 # Mid-Big endian BADC
BYTEORDER_LITTLE_SWAP: int = 3 # Mid-Little endian CDAB

#####################################ERROR CODE HANDLING####################################################
# Error Codes and Lookup Table
error_codes = {
    "ER01": lambda a: a == 0,
    "ER04": lambda a: a > 2 or a < -2,
    "ER03": lambda a: a == 32766,
    "ER06": lambda a: a == -32768,
    "ER07": lambda a: a == 32752,
    "ER08": lambda a: a == 32768,
    "ER10": lambda a: a < 0,
    "ER05": lambda a: isinstance(a, float) and (a - int(a)) != 0,
    "ER14": lambda a: a > 2500,
    "ER20": lambda a: 'e' in format(a, 'g')
}

lookup_table = {
    'json_group1': [
        ((1, 37), ["E"], ["ER01", "ER10", "ER03","ER20"]),
        ((43, 49), ["E"], ["ER01", "ER10", "ER03"]),
        ((38, 42), ["E"], ["ER03", "ER04","ER20"]),
        ((50, 246), ["E"], ["ER03", "ER10"])
    ],
    'json_group2': [
        ((41, 45), ["T"], ["ER03", "ER04", "ER06", "ER07", "ER08","ER20"]),
        ((161, 165), ["T"], ["ER03", "ER04", "ER06", "ER07", "ER08","ER20"]),
        ((81, 85), ["T"], ["ER03", "ER04", "ER06", "ER07", "ER08","ER20"]),
        ((178,178), ["T"], ["ER03", "ER04", "ER06", "ER07", "ER08","ER20"]),
        ((179,179), ["T"], ["ER03", "ER04", "ER06", "ER07", "ER08","ER20"])
    ],
    'json_group3': [
        ((1,28), ["T"], ["ER01", "ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((29,39), ["T"], ["ER03","ER20"]),
        ((44,61), ["T"], ["ER01", "ER03", "ER06", "ER07", "ER08", "ER10"]),
        ((63,68), ["T"], ["ER01", "ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((69,80), ["T"], ["ER03"]),
        ((86,109), ["T"], ["ER01", "ER03", "ER06", "ER07", "ER08", "ER10"]),
        ((136,137), ["T"], ["ER01", "ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((151,151), ["T"], ["ER01", "ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((155, 156), ["T"], ["ER01", "ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((166, 176), ["T"], ["ER01", "ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((181, 192), ["T"], ["ER01", "ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((199, 218), ["T"], ["ER01", "ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((217, 226), ["T"], ["ER01", "ER03", "ER06", "ER07", "ER08", "ER10","ER20"])
    ],
        'json_group4': [
        ((40,40), ["T"], ["ER10","ER20"]),
        ((62,62), ["T"], ["ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((135,135), ["T"], ["ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((160,160), ["T"], ["ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((177,177), ["T"], ["ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((142,150), ["T"], ["ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((152, 160), ["T"], ["ER03", "ER06", "ER07", "ER08", "ER10","ER20"]),
        ((180,180), ["T"], ["ER03", "ER06", "ER07", "ER08", "ER10","ER20"])
    ],
    'json_OLTC': [
        ((138,138), ["T"], ["ER01", "ER05", "ER10","ER20"])
    ]
}

# Fn to determine the group, sol_name(s), and applicable error codes for the given CH_NO and sol_name
def get_error_codes_for_CH_NO_and_sol_name(CH_NO, sol_name):
    for group, ranges in lookup_table.items():
        for r, sol_names, error_list in ranges:
            # Handle both tuple ranges and single value cases
            if isinstance(r, tuple):
                if r[0] <= CH_NO <= r[1] and sol_name in sol_names:
                    return group, error_list
            elif isinstance(r, int) and r == CH_NO and sol_name in sol_names:
                return group, error_list
    return None, []  # Return None if no matching range is found

# Fn to handle the error from respective code 
def handle_error(a, CH_NO, sol_name):
    
    CH_group, applicable_error_codes = get_error_codes_for_CH_NO_and_sol_name(CH_NO, sol_name)

    # If no group or error codes are found for CH_NO and sol_name, return 'a'
    if not CH_group or not applicable_error_codes:
        #a = format(a, '.32f').rstrip('0').rstrip('.')
        return a  

    # Check the conditions of the applicable error codes
    for error_code in applicable_error_codes:
        if error_codes[error_code](a):  
            return f'"{error_code}"'  # Return the first error code that matches the condition

    # If no error code matches, return 'a' instead of None
    #a = format(a, '.32f').rstrip('0').rstrip('.')
    return a

##########################################################################################################


def get_temp_humidity_orange():
    try:
        output = subprocess.check_output(['node_dht11.js'])
        output = output.decode('utf-8').strip()
        temperature_str = output.split('celsius: ')[1].split(' ')[0]
        humidity_str = output.split('humidity: ')[1]
        return temperature_str,humidity_str

    except:
        temperature = "\"ER03\""
        humidity = "\"ER03\""
        return temperature,humidity

def get_temp_humidity_raspberry():
    temperature = "\"ER03\""
    humidity = "\"ER03\""
    # Initialize the DHT device with data pin connected to D4 (Change this according to requirement)
    try:
        dhtDevice = adafruit_dht.DHT11(board.D4)
    #try:
        # Read temperature and humidity values from the sensor
        temperature_c = dhtDevice.temperature
        temperature_f = temperature_c * (9 / 5) + 32
        humidity = dhtDevice.humidity

        # Return the temperature and humidity as a tuple
        return str(temperature_c), str(humidity)

    except Exception as e:
        print(f"{tag} : An error occurred: {str(e)}")
        temperature = "\"ER03\""
        humidity = "\"ER03\""
        return temperature, humidity
    finally:
        dhtDevice.exit()    

def get_temp_humidity_raspberry1():
    temperature = "\"ER03\""
    humidity = "\"ER03\""

    try:
        # Set the sensor type and the GPIO pin number
        sensor = Adafruit_DHT.DHT11
        pin = 4  # GPIO pin number (D4)

        # Read temperature and humidity from the sensor
        humidity, temperature = Adafruit_DHT.read_retry(sensor, pin)

        if humidity is not None and temperature is not None:
            # Temperature is already in Celsius, can be converted to Fahrenheit if needed
            temperature_f = temperature * (9 / 5) + 32
            print(f"Temperature: {temperature} C / {temperature_f} F, Humidity: {humidity}%")
        else:
            print("Failed to retrieve data from the sensor")
            temperature = "\"ER03\""
            humidity = "\"ER03\""
    except Exception as e:
        print(f"Error occurred: {str(e)}")
        temperature = "\"ER03\""
        humidity = "\"ER03\""

    return str(temperature), str(humidity)

# Fn to Set the respective parity values from the master_gateway.yml file 
def get_parity(parity):
    if parity in ['E', 'e']:
        return serial.PARITY_EVEN
    elif parity in ['O', 'o']:
        return serial.PARITY_ODD
    elif parity in ['N', 'n']:
        return serial.PARITY_NONE
    else:
        raise ValueError(f"{tag} : Invalid parity value: {parity} from .yml file")

# Fn to Handle the Modbus exception error codes 
def handle_modbus_errorcodes(data_reader, e, address):
    if isinstance(e, minimalmodbus.NoResponseError):
        data_reader.instrument._print_debug(f"{tag} : No response from slave at address {address}, Reason : {e}.")
        return "\"ER19\""  # Error code for no response from slave
    elif isinstance(e, minimalmodbus.IllegalRequestError):
        data_reader.instrument._print_debug(f"{tag} : Illegal request for address {address}, Reason : {e}.")
        return "\"ER18\""  # Error code for illegal request of address
    elif isinstance(e, minimalmodbus.SlaveDeviceBusyError):
        data_reader.instrument._print_debug(f"{tag} : Slave device busy on address {address}, Reason : {e}.")
        return "\"ER16\""  # Error code for Slave address busy of address
    elif isinstance(e, minimalmodbus.MasterReportedException):
        data_reader.instrument._print_debug(f"{tag} : Master reported issue on address {address}, Reason : {e}.")
        return "\"ER17\""  # Error code for Slave address busy of address
    else:
        data_reader.instrument._print_debug(f"{tag} : Communication error: {e}")
        return "\"ER15\""  # General communication error


def get_mac_address(interface):
    addresses = psutil.net_if_addrs()
    mac_address = addresses[interface][0].address
    return mac_address

# Class for Initialising the Modbus communication
class ModbusReader:
    def connect(self,port,baudrate,parity_connect,stopbits,slave_address,timeout=0.1):
        self.slave_address = slave_address
        self.port = PORT_RS485
        self.instrument = minimalmodbus.Instrument(self.port, self.slave_address)
        self.instrument.serial.baudrate = baudrate
        self.instrument.serial.parity = parity_connect
        self.instrument.serial.stopbits = stopbits
        self.instrument.serial.timeout = timeout
        self.instrument.clear_buffers_before_each_transaction = True
        self.instrument.serial.rs485_mode = RS485Settings(
            rts_level_for_tx=True,   # Set RTS high when transmitting
            rts_level_for_rx=False,  # Set RTS low when receiving
            loopback=False,
            delay_before_tx=0,       # You can adjust according to requirement
            delay_before_rx=0     # You can adjust according to requirement
        )

# Load the YAML configuration file
temperature_key='136'
humidity_key='137'
parameter=""
json_list=[]

# Main function 
if __name__=="__main__":
    data_reader = ModbusReader()

    with open('src/master_gateway.yml', 'r') as file:
        config = yaml.safe_load(file)

    conn_raw, cursor_raw = sqlite_fifo.init_db(db, table_name)

    while True:
        # Add interval to the current time
        start_time = datetime.now()
        nxt_reading_time = start_time + timedelta(seconds=reading_intervl)   
        for slave_config in config['slaves']:
            # Communication settings for the current slave from .yml file 
            communication_settings = slave_config['communication']
            port = communication_settings['port']
            baudrate = communication_settings['baudrate']
            parity = communication_settings['parity']
            stopbits = communication_settings['stopbits']
            parity_connect = get_parity(parity)
           
            print(f"{tag} : Slave Configuration - Port: {port}, Baudrate: {baudrate}, Parity: {parity_connect}, Stop Bits: {stopbits}")
            
            # Slave settings for the current slave from .yml file 
            sensors = slave_config['sensors']
            for sensor in sensors:
                now = datetime.now()
                rounded_seconds = now.strftime("%Y-%m-%d %H:%M:%S")
                time_string="\"created_at\":"+"\""+str(rounded_seconds)+"\""
                slave_address=sensor['slave_address']
                sensor_id = sensor['id']
                registers = sensor['registers']
                header = "startjson00:00:00:00:00:00" 
                footer1="end"
                footer2=f"SensorID:{sensor_id}end"
                print(f"{tag} : Sensor ID: {sensor_id}")
                
                data_reader.connect(port, baudrate, parity_connect, stopbits,slave_address)
                data_reader.instrument.debug = True
                
                for register in registers:
                    print()
                    print("###########################-REGISTER COUNT-###########################")
                    address = register['address']
                    name = str(register['name']).zfill(2)
                    bytes_to_read = register['bytes']
                    data_type=register['data_type']
                    endian=register['endian']
                    f_code=register['function_code']
                    solution_name=register['solution']
                    
                # State Machine by INPUT - datatype
                    # Datatype = 1 : unsigned int 16 bit
                    try:
                        if data_type==1: 
                            print(f"{tag} : Data type is unsigned integer")                       
                            data = data_reader.instrument.read_register(registeraddress=address,
                                                                    number_of_decimals= 0,
                                                                    functioncode=f_code,
                                                                    signed= False,
                                                                    )
                    # Datatype = 2 : signed int 16 bit
                        elif data_type==2:  
                            print(f"{tag} : Data type is signed int")
                            data = data_reader.instrument.read_register(registeraddress=address,
                                                                    number_of_decimals= 0,
                                                                    functioncode=f_code,
                                                                    signed= True,
                                                                    )
                            
                    # Datatype = 3 : Float 32-bit        
                        elif data_type==3:  
                            print(f"{tag} : Data type is float")
                            data=data_reader.instrument.read_float(registeraddress=address,
                                                               functioncode=f_code,
                                                               byteorder= endian,
                                                               number_of_registers=bytes_to_read
                                                               )
                    
                    # Datatype = 4 : Long int 32-bit
                        elif data_type==4:
                            print(f"{tag} : Data type is long")
                            data=data_reader.instrument.read_long(registeraddress=address,
                                                              functioncode=f_code,
                                                              signed= False,
                                                              number_of_registers=bytes_to_read,
                                                              byteorder= endian,
                                                              )
                    # Datatype = 5 : Bit Coil-read        
                        elif data_type==5:  
                            print(f"{tag} : Data type is bits")
                            data=data_reader.instrument.read_bits(registeraddress=address,
                                                              number_of_bits= 1,
                                                              functioncode=f_code
                                                             )
                            # Mapping values to statuses
                            status_map = {0: '"HEALTHY"', 1: '"OPERATED"'}
                            data = status_map.get(data[0], '"UNKNOWN"')

                    except Exception as e:
                        data = handle_modbus_errorcodes(data_reader, e, address)
                    
                    #Error Handling - Seperate each error based on Code
                    #if isinstance(data, str) or isinstance(data, bool) or isinstance(data, list) or isinstance(data, dict):
                    #    data="\"ER03\""
                    
                    print(f"{tag} : Data is {data}")

                    if isinstance(data, float) and math.isnan(data):
                        data = "\"ER91\""
                    elif not isinstance(data, str):
                        data = handle_error(data, int(name), solution_name)

                    print(f"{tag} : Data after  Error check is {data}")
                    parameter=parameter+"\""+solution_name+name+"\":"+str(data)+","
                    print(f"{tag} : Register - Address: {address}, Name: {name}, Bytes to Read: {bytes_to_read}")
                    print(f"{tag} : Data is {data}")
                    time.sleep(0.1)
                    
                # Pushing the string to the database   
                if sensor_id != 0:
                    footer=f"SensorID:{sensor_id}end"   
                    post_data=header+parameter+time_string+footer
                    print(post_data)
                    time.sleep(1)
                    json_list.append(post_data)
                    parameter=""
                else:
                    pass
                  
            if sensor_id==0:
                temperature,humidity=get_temp_humidity_raspberry1()
                parameter=parameter+"\""+solution_name+temperature_key+"\":"+temperature+","
                parameter=parameter+"\""+solution_name+humidity_key+"\":"+humidity+","
                footer="end"
                post_data=header+parameter+time_string+footer
                json_list.append(post_data)
                parameter=""
    

                while len(json_list)>0:
                    popped_data=json_list.pop(0)
                    sqlite_fifo.push_data(cursor_raw, conn_raw, table_name, popped_data)
                    print(popped_data)
            while datetime.now() < nxt_reading_time:
                time.sleep(0.05)
