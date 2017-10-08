# -*- coding: utf-8 -*-
"""
Created on Sun Feb 19 18:28:47 2017

@author: Martin
"""

import os
import numpy as np
from bokeh.layouts import gridplot
from bokeh.plotting import figure, output_file, save, curdoc
from bokeh.models.ranges import Range1d, DataRange1d
from bokeh.models import HoverTool
from bokeh.models import ColumnDataSource
import measure
from datetime import datetime, timedelta
import config
import time

bokeh_timeoffset = timedelta(seconds=2*60*60)

def GetInitialData(stream_flag, start,end,resolution):
    analog, time_analog = measure.GetAnalogDataFromDatabase(start,end,resolution)
    digital, time_digital = measure.GetDigitalDataFromFile(start,end)
    if digital.shape[0] == 0: # vstacking the last line of zero column array results in zero column array       
        if stream_flag:
            digital = measure.GetLastDigitalDataFromFile()
            digital = np.vstack([digital,digital])
            time_digital = np.array([start,datetime.now()]) # no data available => current values equal to values from before
    SpreadDigitalValues(digital)
    return analog, time_analog, digital, time_digital, start
        
def SpreadDigitalValues(data):
    if data.shape[0] != 0:
        for k in range(6): # spread digital plots to make them visible
            data[:,k] = data[:,k]*0.6+(5-k)+0.2
        return data
    else:
        return [[]]
    
def GetDigitalDataDictionaryFromData(digital, time_digital):
    time_digital_bokeh = [t + bokeh_timeoffset for t in time_digital]
    dic_digital = dict(time_=time_digital_bokeh,
                                   d0=digital[:,0],d1=digital[:,1],d2=digital[:,2],
                                   d3=digital[:,3],d4=digital[:,4],d5=digital[:,5],
                                   timestr=[t.strftime('%y-%m-%d %H:%M:%S.%f')[:-5] for t in time_digital])
    return dic_digital
    
def GetAnalogDataDictionaryFromData(analog, time_analog):
    time_analog_bokeh = [t + bokeh_timeoffset for t in time_analog]
    dic_analog = dict(time_=time_analog_bokeh,
                                   a0=analog[:,0],a1=analog[:,1],
                                   timestr=[t.strftime('%y-%m-%d %H:%M:%S.%f')[:-5] for t in time_analog])
    return dic_analog
    
def InitializePlot(stream_flag,start,end,resolution):
    analog, time_analog, digital, time_digital, start = GetInitialData(stream_flag,start,end,resolution)    
    dic_digital = GetDigitalDataDictionaryFromData(digital, time_digital)
    dic_analog = GetAnalogDataDictionaryFromData(analog, time_analog)
    source_digital = ColumnDataSource(dic_digital)    
    source_analog = ColumnDataSource(dic_analog)
    
    tools1 = 'xpan,xwheel_zoom,reset,hover,save,tap'
    p1 = figure(width=800, height=200,tools=tools1, x_axis_type="datetime", active_drag="xpan", title="Digital Input", responsive=True)
    p1.grid.grid_line_alpha=0.3
    p1.y_range = Range1d(0,6.2)
    p1.xaxis.axis_label = 'time'
    p1.ygrid.grid_line_alpha = 1
    p1.ygrid.grid_line_width = 1
    p1.ygrid.grid_line_color = '#000000'
    p1.yaxis.visible = False
    colors = ['#FF0000','#00FF00','#0000FF','#808000','#800080','#20b2aa']
    p1.select_one(HoverTool).tooltips = "@timestr"
    p1.select_one(HoverTool).line_policy = 'nearest' # show nearest datapoint
    for k in range(6):
        p1.line(x='time_', y='d{}'.format(k), color=colors[k], legend=config.channel_names_digital_display[k], line_width=3,source=source_digital)
    p1.legend.location = "top_left"
    
    tools2 = 'pan,wheel_zoom,reset,hover,save,tap'
    p2 = figure(width=800, height=200,tools=tools2,x_axis_type="datetime", active_drag="pan", title=config.channel_names_analog_display[0], responsive=True)
    p2.grid.grid_line_alpha = 0.3
    p2.xaxis.axis_label = 'time'
    p2.yaxis.axis_label = '{} / bar'.format(config.channel_names_analog_display[0])
    p2.select_one(HoverTool).tooltips = [("(x,y)", "(@timestr, @a0)"),]
    p2.select_one(HoverTool).line_policy = 'nearest' # show nearest datapoint
    p2.line(x='time_', y='a0', line_width=3,source=source_analog)
              
    p3 = figure(width=800, height=200,tools=tools2,x_axis_type="datetime", active_drag="pan", title=config.channel_names_analog_display[1], responsive=True)
    p3.grid.grid_line_alpha = 0.3
    p3.xaxis.axis_label = 'time'
    p3.yaxis.axis_label = '{} / mbar'.format(config.channel_names_analog_display[1])
    p3.select_one(HoverTool).tooltips = [("(x,y)", "(@timestr, @a1)"),]
    p3.select_one(HoverTool).line_policy = 'nearest' # show nearest datapoint
    p3.line(x='time_', y='a1', line_width=3,source=source_analog)
    
    if stream_flag:
        p1.x_range = DataRange1d(follow='end',follow_interval=config.rollover_time*1000)
    p2.x_range = p1.x_range
    p3.x_range = p1.x_range
    return p1,p2,p3, analog, time_analog, digital, time_digital, source_analog, source_digital
  
def GenerateBokehPlotHtml(html_path,start,end,resolution):
    stream_flag = False
    p1,p2,p3, analog, time_analog, digital, time_digital, source_analog, source_digital = InitializePlot(stream_flag,start,end,resolution) 
    output_filepath = os.path.join(config.current_filelocation,html_path)
    output_file(output_filepath, title="plot data")
    save(gridplot([[p1],[p2],[p3]], plot_width=800, plot_height=400))
    
def StreamBokehPlot():
    stream_flag = True
    start_init = datetime.fromtimestamp(time.time()-config.rollover_time)
    end_init = datetime.now()
    p1,p2,p3, analog, time_analog, digital, time_digital, source_analog, source_digital = InitializePlot(stream_flag, start_init,end_init,resolution=1)       
    print('time_digital = ')
    print(time_digital)    
    
    def update(): 
        #digital
        nonlocal digital, time_digital
        start = time_digital[-1]   
        end = datetime.now() 
        digital_new, time_digital_new = measure.GetDigitalDataFromFile(start,end,use_only_last_20=True) 
        if len(time_digital_new) == 0:
            time_digital_new = [end]
            digital_new = np.array([digital[-1]])
        else:
            SpreadDigitalValues(digital_new)   
            
        dic_digital_new = GetDigitalDataDictionaryFromData(digital_new, time_digital_new)
        source_digital.stream(dic_digital_new, config.rollover) 
        digital, time_digital = digital_new, time_digital_new 
        #analog
        nonlocal analog, time_analog
        start = time_analog[-1]+timedelta(seconds=1)
        analog_new, time_analog_new = measure.GetAnalogDataFromDatabase(start,end,resolution=1)
        if len(time_analog_new) !=0:             
            dic_analog_new = GetAnalogDataDictionaryFromData(analog_new, time_analog_new)              
            source_analog.stream(dic_analog_new, config.rollover) # follow interval supplied to the stream                   
            analog, time_analog = analog_new, time_analog_new
    curdoc().add_root(gridplot([[p1],[p2],[p3]], plot_width=800, plot_height=400))
    curdoc().add_periodic_callback(update, 1000)
    curdoc().title = "Glovebox dataplot stream"
    update()
