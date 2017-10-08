# -*- coding: utf-8 -*-
"""
Created on Mon Feb 20 03:13:08 2017

@author: Martin
"""

from flask import Flask, render_template, redirect, request
import time
import bokeh_plot, measure, config
import netifaces as ni
from datetime import datetime
import logging, traceback
    
def PrepareDataForHtmlTable(analog, digital):
    key = ['time'] + config.channel_names_digital_display + config.channel_names_analog_display
    value = [datetime.now().strftime("%Y-%m-%d %H:%M:%S")]
    for d in digital:
        value.append('{:.0f}'.format(d))
    value.append('{:.2f} bar'.format(analog[0]))
    value.append('{:.2f} mbar'.format(analog[1]))
    return key, value
    
#logging.basicConfig(level=logging.DEBUG, filename='/home/pi/Desktop/Glovebox_Monitoring/logfiles/webapp.log')
try:    
    app = Flask(__name__)
    ni.ifaddresses('eth0')
    ip = ni.ifaddresses('eth0')[2][0]['addr']
    @app.route('/', methods=['POST','GET'])
    def index():
        if request.method == 'POST':
            resolution = request.form['resolution']
            timespan = request.form['timespan']
            print('resulution = {}'.format(resolution))
            print('timespan = {}'.format(timespan))
            start = datetime.fromtimestamp(int(time.time()-float(timespan))).isoformat(' ')
            end = datetime.fromtimestamp(int(time.time())).isoformat(' ')
            return redirect('/plot_data/{}/{}/{}'.format(start,end,resolution))
        else:
            print(request.method)
            resolution = 3600
            print('resolution = {}'.format(resolution))
            analog = measure.GetLastAnalogDataFromDatabase()
            digital = measure.GetLastDigitalDataFromFile()
            key, value = PrepareDataForHtmlTable(analog[0],digital[0])
            database_path_analog = '/static/{}?time={}'.format(config.database_name_analog,time.time()) # avoid caching
            datafile_path_digital = '/static/{}?time={}'.format(config.datafile_name_digital,time.time()) # avoid caching
            return render_template('index.html',key=key,value=value,
                                   database_path_analog=database_path_analog,
                                   datafile_path_digital=datafile_path_digital,
                                   glovebox_name=config.glovebox_name)
    @app.route('/stream')
    def stream():
        return redirect('http://' + ip + ':5006')
    @app.route('/rpimonitor')
    def rpimonitor():
        return redirect('http://' + ip + ':8888')
    @app.route('/plot_data/<start>/<end>/<resolution>') # resolution in seconds, timespan in seconds
    def plot_data(start,end,resolution):
        start_d = datetime.strptime(start, "%Y-%m-%d %H:%M:%S")
        end_d = datetime.strptime(end, "%Y-%m-%d %H:%M:%S")
        resolution_int = int(resolution)
        number_of_datapoints = (end_d-start_d).total_seconds()/resolution_int
        print('number of datapoints = {}'.format(number_of_datapoints))
        if number_of_datapoints > 1E6:
            return redirect('/warning')
        else:
            bokeh_plot.GenerateBokehPlotHtml("templates/plot_data.html",start_d,end_d,resolution_int)
            return render_template('plot_data.html')
    @app.route('/info_about')
    def info_about():
        return render_template('info_about.html')
    @app.route('/warning')
    def warning():
        return render_template('warning.html',glovebox_name=config.glovebox_name)
    app.run(debug=True, host='0.0.0.0', port=11111)
except:
    #logging.exception("Error in webapp.py:")
    traceback.print_exc()
