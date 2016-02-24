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
Uses the Dark Sky API to get weather at current location

Requires a Dark Sky API key. Visit them to get one: https://developer.forecast.io
Uses http://ipinfo.io to look up current location
"""

import os
import urllib
import datetime
import json

DARKSKY_API_KEY = None
DARKSKY_URL = "https://api.forecast.io/forecast/%s/%s,%s?exclude=minutely,alerts,flags"
DARKSKY_URL_NO_TIME = "https://api.forecast.io/forecast/%s/%s?exclude=minutely,alerts,flags"

if not DARKSKY_API_KEY and 'DARKSKY_API_KEY' in os.environ:
    DARKSKY_API_KEY = os.environ['DARKSKY_API_KEY']

if not DARKSKY_API_KEY:
    raise Exception("DARKSKY_API_KEY missing for weather data")


def get_daytime_weather_data(log, weather_time=None, location=None):
    """
    Get average weather during daytime hours

    :param log: Pass in if you want log output @ debug level
    :param weather_time: YYYYMMDD to get weather for
    """

    if not location:
        # Get current location
        try:
            l = json.load(urllib.urlopen('http://ipinfo.io/json'))
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
        fp = urllib.urlopen(DARKSKY_URL % (DARKSKY_API_KEY, location, int(weather_time)))
    else:
        fp = urllib.urlopen(DARKSKY_URL_NO_TIME % (DARKSKY_API_KEY, location))

    data = ""
    # Get weather data and convert json to dict
    while True:
        d = fp.read()
        if not d:
            break
        data += d

    try:
        weather = json.loads(data)
    except:
        raise Exception("Can't decode Dark Sky weather data response:\n%s" % data)

    if log:
        # Uncomment if you want to see the gory details
        pass
        # log.debug("Weather details: %s", weather)

    # Now compute average cloud coverage/temperature for the day
    cc_total = 0.0
    cc_count = 0
    cc_average = 0
    temp_total = 0.0
    temp_count = 0
    temp_average = 0
    low_temp = 200
    cloudcover = 0

    for h in weather["hourly"]["data"]:
        # Find daytime average cloud cover
        if "cloudCover" in h:
            if h["time"] > weather["daily"]["data"][0]["sunriseTime"] \
                    and h["time"] < weather["daily"]["data"][0]["sunsetTime"]:
                cc_total += h["cloudCover"]
                cc_count += 1

        # Find daytime average temperature
        if "temperature" in h:
            if h["time"] > weather["daily"]["data"][0]["sunriseTime"] \
                    and h["time"] < weather["daily"]["data"][0]["sunsetTime"]:
                temp_total += h["temperature"]
                temp_count += 1
                if h["temperature"] < low_temp:
                    low_temp = h["temperature"]

    if cc_count:
        cc_average = (100.0 * cc_total) / cc_count

    if temp_count:
        temp_average = temp_total / temp_count

    # Get total day cloud cover reported
    if "cloudCover" in weather["daily"]["data"][0]:
        cloudcover = weather["daily"]["data"][0]["cloudCover"] * 100

    if log:
        log.debug("cloudCoverage Day: %d%%, Cloud Coverage daytime average: %d%%", cloudcover, cc_average)

    # Compute hours of daylight
    daylight = (weather["daily"]["data"][0]["sunsetTime"] - weather["daily"]["data"][0]["sunriseTime"]) / 60.0 / 60.0

    # Build results
    weather_info["cloud_cover"] = cc_average
    weather_info["daylight"] = daylight
    weather_info["description"] = weather["daily"]["data"][0]["summary"]
    weather_info["avg_temp"] = temp_average
    weather_info["low_temp"] = low_temp
    weather_info["current_temp"] = weather["currently"]["temperature"]

    # Return precipitation probability in a useful form
    if "precipProbability" in weather["daily"]["data"][0]:
        weather_info["precip_probability"] = weather["daily"]["data"][0]["precipProbability"] * 100.0
    else:
        weather_info["precip_probability"] = 0.0
    if "precipType" in weather["daily"]["data"][0]:
        weather_info["precip_type"] = weather["daily"]["data"][0]["precipType"]
    else:
        weather_info["precip_type"] = "none"
    return weather_info
