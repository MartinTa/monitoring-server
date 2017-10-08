#!/bin/sh

GUNICORN=/usr/local/bin/gunicorn
ROOT=/home/pi/Desktop/Glovebox_Monitoring/
APP=webapp:app

cd $ROOT
exec $GUNICORN --error-logfile logfiles/gunicorn.log --capture-output $APP
