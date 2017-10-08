# -*- coding: utf-8 -*-
"""
Created on Mon Feb 20 03:13:08 2017

@author: Martin
"""

import os
import time
import RPi.GPIO as GPIO
import Adafruit_GPIO.SPI as SPI
import Adafruit_MCP3008
import numpy as np
import config
import rrdtool
from datetime import datetime
import dateutil.parser
import logging, traceback
    
def GetDigitalDataFromLines(lines):
    time_ = [dateutil.parser.parse(line.split(';')[0]) for line in lines]
    data_digital = np.array([line.split(';')[1:] for line in lines],dtype=np.float32)
    digital = np.kron(data_digital,np.ones([2,1]))[:-1] # to plot straight line over time until next change
    time_digital = [i for sub in zip(time_,time_) for i in sub][1:]
    return digital, time_digital
        
def GetAllDigitalDataFromFile():
    with open(config.datafile_path_digital, 'r', os.O_NONBLOCK) as f:
        lines = f.readlines()[1:]
    if len(lines) == 0:
        print('No data measured! Exiting...')
        exit()
    return GetDigitalDataFromLines(lines)
    
def GetDigitalDataFromFile(start,end,use_only_last_20 = False):
    with open(config.datafile_path_digital, 'r', os.O_NONBLOCK) as f:
        if use_only_last_20:
            lines = f.readlines()[-20:]
            if 'time' in lines[0]:
                lines = lines[1:]
        else:
            lines = f.readlines()[1:]
    if len(lines) == 0:
        return np.zeros([0,6]), [], False 
    times = [dateutil.parser.parse(line.split(';')[0]) for line in lines]
    times_np = np.array([(t-datetime(1970,1,1,1)).total_seconds() for t in times])
    start_np = np.array((start-datetime(1970,1,1,1)).total_seconds())
    end_np = np.array((end-datetime(1970,1,1,1)).total_seconds())
    valid_indices = np.where(np.logical_and(times_np>start_np,times_np<end_np))[0]
    if valid_indices.size == 0: # in case no measured data in intervall
        return np.zeros([0,6]), np.array([])
    else:
        start_ind, stop_ind = valid_indices[0]-1, valid_indices[-1]+1
        if start_ind == -1:
            start_ind = 0
        lines_cut = lines[start_ind:stop_ind]
        digital, time_digital = GetDigitalDataFromLines(lines_cut)
        if start_ind != 0 and len(time_digital) >1:
            time_digital[0] = time_digital[1]
        return digital, time_digital
    
def GetLastDigitalDataFromFile():
    with open(config.datafile_path_digital, "r", os.O_NONBLOCK) as f:
        line = f.readlines()[-1]
    return np.array([line.split(';')[1:]],dtype=np.float32)

def GetAnalogDataFromDatabase(start,end,resolution): # resolution in seconds
    # align start and end with fetchable time
    start_time = int(time.mktime(start.timetuple())/resolution)*resolution
    end_time = int(time.mktime(end.timetuple())/resolution)*resolution
#    t1 = time.time()
#    print('fetching...')
    result = rrdtool.fetch(config.database_path_analog, "AVERAGE","-r",
                           str(resolution),"--start",str(start_time),"--end",str(end_time)) 
#    t2 = time.time()
#    print('time to fetch: {}'.format(t2-t1))
    start_r, end_r, step_r = result[0]
    data = np.round(np.array(result[2],dtype=np.float64)*1000)/1000
#    t3 = time.time()
#    print('time to round: {}'.format(t3-t2))
    time_s = np.linspace(start_r,end_r-1,len(result[2]))
    
#    t4 = time.time()    
    index_all = np.where(np.invert(np.isnan(data[:,0])))
    if len(index_all[0]) == 0: #no useful data in timerange
        return np.zeros([0,2]),[]
    else:
        first = index_all[0][0]
        last = index_all[0][-1]
        data_trim = data[first:last+1,:]
        time_s_trim = time_s[first:last+1]
#        t5 = time.time()
#        print('time to cut: {}'.format(t5-t4))    
        time_ = [datetime.fromtimestamp(t) for t in time_s_trim] 
#        print('time to make timestamp: {}'.format(time.time()-t5))
        return data_trim, time_
        
def GetLastAnalogDataFromDatabase():
    result = rrdtool.lastupdate(config.database_path_analog)
    datasource = result['ds']
    data = np.array([[datasource[name] for name in config.channel_names_analog]],dtype=np.float32)
    return data    
    
    
def MeasureData(mcp):
    time_ = datetime.now()
    digital = np.array([GPIO.input(pin) for pin in config.GPIO_pins],dtype=np.int8)
    volts_at_PCB = np.array([int(mcp.read_adc(4)),int(mcp.read_adc(6))])*5./615 # between 0 and 5 V
    argon_pressure = config.Volts_at_PCB_to_Ar_pressure(volts_at_PCB[0]) # bar
    glovebox_pressure = config.Volts_at_PCB_to_Glovebox_pressure(volts_at_PCB[1]) # mbar
    analog = np.array([argon_pressure,glovebox_pressure],dtype=np.float32)#'{};{:.0f};{:.0f}'.format(digital,argon_pressure,glovebox_pressure)
    return digital, analog, time_
    
def SendEmail():
    from email.header    import Header
    from email.mime.text import MIMEText
    from smtplib         import SMTP_SSL
    # create message
    msg = MIMEText(config.email_text, 'plain', 'utf-8')
    msg['Subject'] = Header(config.email_header, 'utf-8')
    msg['From'] = config.login
    msg['To'] = ", ".join(config.recipients)
    # send it via gmail
    s = SMTP_SSL('smtp.gmail.com', 465, timeout=10)
    s.set_debuglevel(1)
    try:
        s.login(config.login, config.password)
        s.sendmail(msg['From'], config.recipients, msg.as_string())
    except:
        logging.exception("Sending Email failed:")
    finally:
        s.quit()

        
def CreateDatabase(): # for analog data
    n_days = 365
    datasources = ['DS:{}:GAUGE:1:U:U'.format(s) for s in config.channel_names_analog] # heartbear:min:max
    rrdtool.create(
        config.database_path_analog,
        "--start", "now",
        "--step", "1", # seconds
        "RRA:AVERAGE:0.5:{}:{}".format(1,60*60*24*n_days), # xff:steps:(rows or duration) 
        "RRA:AVERAGE:0.5:{}:{}".format(60,60*24*n_days), # xff:steps:(rows or duration) 
        "RRA:AVERAGE:0.5:{}:{}".format(60*60,24*n_days),
        *datasources)

def main():
    #setup logging
    logging.basicConfig(level=logging.DEBUG, filename='/home/pi/Desktop/Glovebox_Monitoring/logfile.txt')
    #setup GPIO
    GPIO.setmode(GPIO.BCM)
    for pin in config.GPIO_pins:
        GPIO.setup(pin, GPIO.IN, GPIO.PUD_DOWN)
    #setup static folder if necessary
    directory = os.path.split(config.database_path_analog)[0]
    if not os.path.exists(directory):
        os.makedirs(directory)
    #setup database
    if not os.path.isfile(config.database_path_analog): #does database already exist?
        CreateDatabase()
        print('database created, Info:')
    else:
        print('database continued, Info:') 
    for key, value in rrdtool.info(config.database_path_analog).items():
        print('{} : {}'.format(key,value))
    print('rrdtool.lib_version = ' + rrdtool.lib_version())        
    #setup datafile
    if not os.path.isfile(config.datafile_path_digital): #does file already exist?
        file_digital = open(config.datafile_path_digital, 'a', os.O_NONBLOCK)
        file_digital.write(';'.join(['time']+config.channel_names_digital) + '\n') # writing header
        file_digital.write(';'.join([datetime.now().isoformat(' ')[:-5],*['-1']*6]))
    else:
        file_digital = open(config.datafile_path_digital, 'a', os.O_NONBLOCK)
    #setup spi
    SPI_PORT   = 0
    SPI_DEVICE = 0
    mcp = Adafruit_MCP3008.MCP3008(spi=SPI.SpiDev(SPI_PORT, SPI_DEVICE))
    print('measuring..')
    digital = np.ones(6,dtype=np.int8)*-1
    sending_email_possible = False
    while 1:
        time_before = time.time()
        digital_new, analog_new, time_new = MeasureData(mcp)
        argon_pressure = analog_new[0]
        if argon_pressure > config.Ar_hysteresis_for_email[1]:
            sending_email_possible = True
        if argon_pressure < config.Ar_hysteresis_for_email[0] and sending_email_possible == True:
            SendEmail()
            print('Argon pressure < {} bar!!!, Email sent!'.format(config.Ar_hysteresis_for_email[0]))
            sending_email_possible = False
        if any(digital_new != digital):
            time_str = time_new.isoformat(' ')[:-5] # with accuracy of thents of a second
            digital_str = ';'.join([str(d) for d in digital_new])
            print(digital_str)
            file_digital.write('{};{}\n'.format(time_str,digital_str))
            file_digital.flush()
            digital = digital_new
        time_rrd = '{:.3f}'.format(time.time())
        rrdtool.update(config.database_path_analog,'{}:{}:{}'.format(time_rrd,analog_new[0],analog_new[1])) # N means current time
        time_delta = 0.1 - (time.time()-time_before)
        if time_delta < 0:
            print('WARNING: Measurement loop not fast enough: time_delta = {}!'.format(time_delta))
        else:
            time.sleep(time_delta) # ms
            
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, filename='/home/pi/Desktop/Glovebox_Monitoring/logfiles/measure.log')
    try:
        main()
    except:
        traceback.print_exc()
        print('Is the ADC properly connected via spi?')
        logging.exception("Error in measure.py:")
