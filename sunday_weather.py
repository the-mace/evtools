#!/usr/bin/env python
# encoding: utf-8
"""
sunday_weather.py

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

Description:

Output a CSV list of the weather on every Sunday of current (or passed) year
"""

import argparse
import time
import datetime
from tl_weather import get_daytime_weather_data

import logging
logging.basicConfig(level=logging.ERROR)


def main():
    parser = argparse.ArgumentParser(description='Show sunday weather start of current (or passed) year to today')
    parser.add_argument('--year', help='Starting year (YYYY)', required=False,
                        default=datetime.datetime.now().year, type=int)
    args = parser.parse_args()

    t = datetime.datetime.strptime("%04d01012100" % args.year, "%Y%m%d%H%M")
    current_year = t.year
    print "date,avg temp,low temp,cloud cover,precip type,precip probability"
    while t.year == current_year and t < datetime.datetime.now():
        ts = "%04d%02d%02d" % (t.year, t.month, t.day)
        if t.weekday() == 6:
            w = get_daytime_weather_data(logging, time.mktime(t.timetuple()))
            print "%s,%.1f,%.1f,%d%%,%s,%d%%" % (ts, w["avg_temp"], w["low_temp"], w["cloud_cover"],
                                                 w["precip_type"], w["precip_probability"])

        t = t + datetime.timedelta(days=1)


if __name__ == '__main__':
    main()
