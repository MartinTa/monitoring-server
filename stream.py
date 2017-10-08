# -*- coding: utf-8 -*-
"""
Created on Wed Feb 22 11:15:52 2017

@author: pi
"""

import bokeh_plot
import logging

def main():
    bokeh_plot.StreamBokehPlot()
if __name__ == '__main__':
    logging.basicConfig(level=logging.DEBUG, filename='/home/pi/Desktop/Glovebox_Monitoring/logfiles/stream.log')
    try:
        main()
    except:
        logging.exception("Error in stream.py:")