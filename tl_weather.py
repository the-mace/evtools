#!/usr/bin/env python
# encoding: utf-8
"""
tl_weather.py

Copyright (c) 2015 Rob Mason

Permission is hereby granted, free of charge, to any person obtaining a copy of this software and associated
documentation files (the "Software"), to deal in the Software without restriction, including without limitation the
rights to use, copy, modify, merge, publish, distribute, sublicense, and/or sell copies of the Software,
and to permit persons to whom the Software is furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all copies or substantial portions of the
Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE
WARRANTIES OF MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE AUTHORS OR
COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

Twitter: @Teslaliving
Blog: http://teslaliving.net

Description:
Uses the WEATHERAPI API to get weather at current location

Requires a WEATHERAPI API key. Visit them to get one: https://www.weatherapi.com
Uses http://ipinfo.io to look up current location
"""

import os
import urllib.request, urllib.parse, urllib.error
import datetime
import json

WEATHERAPI_API_KEY = None
WEATHERAPI_URL = "https://api.weatherapi.com/v1/history.json?key=%s&q=%s&dt=%s"
WEATHERAPI_URL_NO_TIME = "https://api.weatherapi.com/v1/current.json?key=%s&q=%s&aqi=no"

if not WEATHERAPI_API_KEY and 'WEATHERAPI_API_KEY' in os.environ:
    WEATHERAPI_API_KEY = os.environ['WEATHERAPI_API_KEY']

if not WEATHERAPI_API_KEY:
    raise Exception("WEATHERAPI_API_KEY missing for weather data")


def get_daytime_weather_data(log, weather_time=None, location=None):
    """
    Get average weather during daytime hours

    :param log: Pass in if you want log output @ debug level
    :param weather_time: YYYY-MM-DD to get weather for
    """

    if not location:
        # Get current location
        try:
            l = json.load(urllib.request.urlopen('http://ipinfo.io/json'))
            location = l["loc"]
            if log:
                log.debug("Get weather data for %s (%s) at %s",
                          l["city"], location, datetime.datetime.fromtimestamp(weather_time))
        except:
            # Default to Statue of Liberty in NY if we can't get current location
            location = "40.689249,-74.0445"

    # Now get the weather at this location
    weather_info = {}

    if weather_time:
        fp = urllib.request.urlopen(WEATHERAPI_URL % (WEATHERAPI_API_KEY, location, weather_time))
    else:
        fp = urllib.request.urlopen(WEATHERAPI_URL_NO_TIME % (WEATHERAPI_API_KEY, location))

    data = fp.read()
    try:
        weather = json.loads(data)
    except:
        raise Exception("Can't decode weather data response:\n%s" % data)

    if log:
        # Uncomment if you want to see the gory details
        pass
        # log.debug("Weather details: %s", weather)

    # Compute hours of daylight
    daylight = 0
    if "forecast" in weather and "forecastday" in weather["forecast"] and \
            "astro" in weather["forecast"]["forecastday"][0]:
        astro = weather["forecast"]["forecastday"][0]["astro"]
        sunrise = datetime.datetime.strptime(astro["sunrise"], '%I:%M %p')
        sunset = datetime.datetime.strptime(astro["sunset"], '%I:%M %p')
        daylight = (sunset - sunrise).total_seconds() / 60.0 / 60.0

    if "forecast" in weather and "forecastday" in weather["forecast"]:
        day_weather = weather["forecast"]["forecastday"][0]["day"]
        weather_info["cloud_cover"] = day_weather['condition']['text']
        weather_info["daylight"] = daylight
        weather_info["description"] = day_weather['condition']['text']
        weather_info["avg_temp"] = day_weather['avgtemp_f']
        weather_info["low_temp"] = day_weather['mintemp_f']
        weather_info["high_temp"] = day_weather['maxtemp_f']

    if "current" in weather:
        day_weather = weather["current"]
        weather_info["cloud_cover"] = day_weather['condition']['text']
        weather_info["description"] = day_weather['condition']['text']
        weather_info["current_temp"] = day_weather["temp_f"]

    return weather_info
