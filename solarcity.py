#!/usr/bin/env python
# encoding: utf-8
"""
solarcity.py

Copyright (c) 2015, 2016 Rob Mason

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

SolarCity doesn't offer an API to access your generation data, so here we're using Selenium to get data the data.

You need to download and install Selenium from here:
    pip install selenium

You also need Mozilla Marionette
    https://developer.mozilla.org/en-US/docs/Mozilla/QA/Marionette/WebDriver
    Download and copy binary to /usr/local/bin and make sure its executable

Other requirements:
    https://github.com/the-mace/evtools

Supply your SolarCity login information via environment variables:
    SOLARCITY_USER
    SOLARCITY_PASSWORD

Examples:
    ./solarcity.py --daily  - Provide end of day update on generation
    ./solarcity.py --report - Send weekly report
    ./solarcity.py --blog - Create blog summary

    See --help output for more options

I use cron to run a bunch of these, example:
00      21       *       *       * source ~/.bashrc;cd "~/Documents/Data";/usr/bin/python ~/Documents/Code/evtools/solarcity.py --daily

Note: There are some "teslaliving" references in the below. Search and change them as desired.
"""

import os
import argparse
import fcntl
import time
import urllib.request, urllib.parse, urllib.error
import urllib.request, urllib.error, urllib.parse
import logging
from logging.handlers import RotatingFileHandler
import traceback
from tl_tweets import tweet_string, tweet_price
from tl_email import email
from selenium import webdriver
import csv
import json
import datetime
from dateutil.relativedelta import relativedelta
import calendar
import random
from tl_weather import get_daytime_weather_data

# Wait time for page loads
PAGE_LOAD_TIMEOUT = 240 * 1000

# Main URL to SolarCity
AUTH_URL = 'https://login.solarcity.com/account/SignIn'

# Where logging output from this tool goes. Modify path as needed
LOGFILE = os.environ.get('LOGFILE')
if not LOGFILE:
    LOGFILE = os.path.expanduser("~/script/logs/solarcity.log")

# Data file containing all the saved state information
DATA_FILE = "solarcity.json"

# Some of the tweets attach pictures. They're randomly chosen from this path
PICTURES_PATH = "images/solar"

# Logging setup
DEF_FRMT = "%(asctime)s : %(levelname)-8s : %(funcName)-25s:%(lineno)-4s: %(message)s"
loglevel = logging.DEBUG
log = logging.getLogger("SolarCity")
loghandler = RotatingFileHandler(LOGFILE, maxBytes=5 * 1024 * 1024, backupCount=8)
loghandler.setFormatter(logging.Formatter(DEF_FRMT))
log.addHandler(loghandler)
log.setLevel(loglevel)

# Get the collection of pictures
SOLAR_IMAGES = []
if os.path.exists(PICTURES_PATH):
    SOLAR_IMAGES = [os.path.join(PICTURES_PATH, f) for f in os.listdir(PICTURES_PATH) if not f.startswith('.')]

# Set to true to disable tweets/data file updates
DEBUG_MODE = False

# Get SolarCity.com login information from environment
if not 'SOLARCITY_USER' in os.environ:
    raise Exception("SOLARCITY_USER missing")
else:
    SOLARCITY_USER = os.environ['SOLARCITY_USER']

if not 'SOLARCITY_PASSWORD' in os.environ:
    raise Exception("SOLARCITY_PASSWORD missing")
else:
    SOLARCITY_PASSWORD = os.environ['SOLARCITY_PASSWORD']


def get_current_day_data():
    driver = webdriver.Chrome()
    driver.implicitly_wait(30)

    try:
        driver.get('https://login.solarcity.com/logout')
    except:
        pass

    time.sleep(10)
    driver.get(AUTH_URL)
    time.sleep(10)
    driver.find_element_by_id("username").send_keys(SOLARCITY_USER)
    password = driver.find_element_by_id("password")
    password.send_keys(SOLARCITY_PASSWORD)
    password.submit()
    time.sleep(10)
    driver.find_element_by_xpath("//div[@id='HomeCtrlView']/div[2]/div/div/a").click()

    production = 0
    daylight_hours = 0
    cloud_cover = 0
    loops = 1

    while loops > 0:
        time.sleep(10)

        data = driver.find_element_by_css_selector("div.consumption-production-panel").text
        data += driver.find_element_by_css_selector("div.details-panel.pure-g").text
        log.debug("raw data: %r", data)

        fields = data.split("\n")

        for f in fields:
            if f.find("hrs") != -1:
                try:
                    daylight_hours = float(f.split()[0])
                    continue
                except:
                    pass
            if f.find(" %") != -1:
                try:
                    cloud_cover = int(f.split()[0])
                    continue
                except:
                    pass
            if f.find("kWh") != -1:
                try:
                    production = float(f.split()[0])
                    continue
                except:
                    pass

        if production != 0:
            break
        loops -= 1

    if float(production) == 0 and cloud_cover == 0 and daylight_hours == 0:
        raise Exception("Problem getting current production level: %.1f, %d, %.1f" % (production,
                                                                                      cloud_cover, daylight_hours))

    if daylight_hours == 0:
        """
        SolarCity has had outages where they cant provide the cloud cover/weather information.
        If the weather data appears empty here, we'll go get it from another source
        """
        w = get_daytime_weather_data(log, time.time())
        cloud_cover = w["cloud_cover"]
        daylight_hours = w["daylight"]

    try:
        driver.find_element_by_xpath("//ul[@id='mysc-nav']/li[18]/a/span").click()
    except:
        pass
    time.sleep(2)

    # If we get here everything worked, shut down the browser
    driver.quit()

    if os.path.exists("geckodriver.log"):
        os.remove("geckodriver.log")

    return daylight_hours, cloud_cover, production


def solar_image():
    if SOLAR_IMAGES:
        return random.choice(SOLAR_IMAGES)


def tweet_production(daylight_hours, cloud_cover, production, special):
    if special == "high":
        extra = "A new high record :) "
    elif special == "low":
        extra = ":( A new low "
    else:
        extra = ""

    if daylight_hours > 0.0:
        message = "Todays @SolarCity Production: %s with %.1f hrs of daylight and %d%% cloud cover. %s" \
                  "#gosolar #bot" % \
                  (show_with_units(production), daylight_hours, cloud_cover, extra)
    else:
        message = "Todays @SolarCity Production: %s (daylight/cloud cover not reported) %s" \
                  "#gosolar #bot" % \
                  (show_with_units(production), extra)

    if DEBUG_MODE:
        print("Would tweet:\n%s" % message)
        log.debug("DEBUG mode, not tweeting: %s", message)
    else:
        media = solar_image()
        log.debug("Using media: %s", media)
        tweet_string(message=message, log=log, media=media)


def tweet_month(data):
    generated_this_week, generated_this_month, generated_this_year, total_generation = compute_generation_data(data)

    message = "This months @SolarCity Production was %s. %s generated in the last 365 days. #gosolar #bot" % \
              (show_with_units(generated_this_month), show_with_units(generated_this_year))
    if DEBUG_MODE:
        print("Would tweet:\n%s" % message)
        log.debug("DEBUG mode, not tweeting: %s", message)
    else:
        tweet_string(message=message, log=log, media=solar_image())


def tweet_year(data):
    generated_this_week, generated_this_month, generated_this_year, total_generation = compute_generation_data(data)

    message = "This years @SolarCity Production was %s! %s generated since install :) #gosolar #bot" % \
              (show_with_units(generated_this_year), show_with_units(total_generation))
    if DEBUG_MODE:
        print("Would tweet:\n%s" % message)
        log.debug("DEBUG mode, not tweeting: %s", message)
    else:
        tweet_string(message=message, log=log, media=random.choice(SOLAR_IMAGES))


def load_data():
    if os.path.exists(DATA_FILE):
        log.debug("Loading existing Solarcity database")
        data = json.load(open(DATA_FILE, "r"))
        log.debug("   %d entries loaded", len(data['data']))
        # Manual insertion if needed
        #data['data']['20150620'] = {'production': 61.5, 'cloud': 68, 'daylight': 15.3}

    else:
        log.debug("No existing Solarcity database found")
        data = {'config': {'lastdailytweet': '20010101'}, 'data': {}}
    return data


def load_historical_data(data):
    """
    This lets you export historical data from SolarCity.com and import it into this tool to
    combine old data with current data.

    Go to your mySolarCity page and download the PowerGuide data and put it in historical.csv
    """
    if len(data['data']) < 5 and os.path.exists('historical.csv'):
        # Only need to load it once
        log.debug("Loading historical data")
        with open('historical.csv') as csvfile:
            reader = csv.DictReader(csvfile)
            for row in reader:
                if row['Energy In Interval (kWh)'] == 'NULL':
                    continue
                process_date = "%s%s%s" % (row['Timestamp'][0:4], row['Timestamp'][5:7], row['Timestamp'][8:10])
                if process_date in data['data']:
                    if 'cloud' not in data['data'][process_date]:
                        data['data'][process_date]['production'] += float(row['Energy In Interval (kWh)'])
                else:
                    data['data'][process_date] = {'production': float(row['Energy In Interval (kWh)'])}
    else:
        log.debug("Skipping load of historical data")
    return data


def analyze_data(data):
    production_max = 0
    production_max_day = None
    production_min = 999999
    production_min_day = None
    total_generation = 0

    for day in data['data']:
        d = data['data'][day]
        # Special handling here where SolarCity provided data thats not credible
        if day in ('20150610',):
            # Bad data days
            continue
        total_generation += d['production']
        if d['production'] > production_max:
            production_max = d['production']
            production_max_day = day
        if d['production'] < production_min:
            production_min = d['production']
            production_min_day = day

    log.debug("Max: %s on %s, Min: %s on %s." % (show_with_units(production_max), production_max_day,
                                                 show_with_units(production_min), production_min_day))
    log.debug("Total: %s" % show_with_units(total_generation))
    return production_max_day, production_min_day, total_generation


def analyze_weather(data):
    """
    SolarCity has had outages where they cant provide the cloud cover/weather information.
    This compares SolarCity reported weather data with other weather data.
    """
    for day in sorted(data['data']):
        d = data['data'][day]
        if "weather_api" not in d:
            time_value = time.mktime(time.strptime("%s2100" % day, "%Y%m%d%H%M"))
            w = get_daytime_weather_data(log, time_value)
            cloud_cover = w["cloud_cover"]
            daylight_hours = w["daylight"]
            if 'cloud' in d:
                ss_cloud = d['cloud']
            else:
                ss_cloud = 0
            if 'daylight' in d:
                ss_daylight = d['daylight']
            else:
                ss_daylight = 0

            print("%s Cloud: %d%% Daylight: %.1f (API Cloud: %d%%, Daylight: %.1f)" % (day, ss_cloud,
                                                                                       ss_daylight, cloud_cover,
                                                                                       daylight_hours))
        else:
            if 'cloud' in d:
                cloud_cover = d['cloud']
            else:
                cloud_cover = 0
            if 'daylight' in d:
                daylight_hours = d['daylight']
            else:
                daylight_hours = 0
            print("%s API Cloud: %d%% API Daylight: %.1f" % (day, cloud_cover, daylight_hours))


def save_data(data):
    log.debug("Save Solarcity database")
    if not DEBUG_MODE:
        json.dump(data, open(DATA_FILE + ".tmp", "w"))
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        os.rename(DATA_FILE + ".tmp", DATA_FILE)
    else:
        log.debug("   Skipped saving due to debug mode")


def show_with_units(generation):
    for units in ('kWh', 'MWh', 'GWh'):
        if generation < 1000:
            break
        generation /= 1000
    message = "{:,.1f}".format(generation)
    message += " " + units
    return message


def compute_generation_data(data):
    w = datetime.date.today() - datetime.timedelta(days=7)
    this_week = int(w.strftime("%Y%m%d"))

    m = datetime.date.today() - datetime.timedelta(days=30)
    this_month = int(m.strftime("%Y%m%d"))

    y = datetime.date.today() - datetime.timedelta(days=365)
    this_year = int(y.strftime("%Y%m%d"))

    generated_this_week = 0
    generated_this_month = 0
    generated_this_year = 0
    total_generation = 0

    log.debug("   This week: %d, last month: %d, last year: %d", this_week, this_month, this_year)

    for a in data['data']:
        production = data['data'][a]['production']
        total_generation += production

        if int(a) > this_week:
            generated_this_week += production
        if int(a) > this_month:
            generated_this_month += production
        if int(a) > this_year:
            generated_this_year += production

    return generated_this_week, generated_this_month, generated_this_year, total_generation


def solarcity_report(data, no_email=False, no_tweet=False):
    log.debug("Report on SolarCity Generation")
    generated_this_week, generated_this_month, generated_this_year, total_generation = compute_generation_data(data)

    message = "Hi there, below is the weekly SolarCity generation report:\n\n"
    message += "Total production this week: %s\n" % show_with_units(generated_this_week)
    message += "Total production in the last 30 days: %s\n" % show_with_units(generated_this_month)

    message += "Total production in the last 365 days: %s\n" % show_with_units(generated_this_year)

    message += "\nLifetime generation is %s.\n" % show_with_units(total_generation)
    message += "\nRegards,\n"
    message += "Teslaliving\nhttp://teslaliving.net"

    if no_email or DEBUG_MODE:
        print("Would email message:\n%s" % message)
    else:
        log.debug("   email report")
        email(email=SOLARCITY_USER, message=message, subject="Weekly SolarCity Report")

    if not no_tweet:
        tweet_message = "%s generated last week with @SolarCity. " % show_with_units(generated_this_week)
        tweet_message += "%s generated in the last 30 days. #GoSolar #bot" % show_with_units(generated_this_month)
        if DEBUG_MODE:
            print("Would Tweet string:\n%s" % tweet_message)
        else:
            tweet_string(message=tweet_message, log=log, media=solar_image())


def upload_to_pvoutput(data, day):
    # Get pvoutput.org login information from environment
    if 'PVOUTPUT_ID' not in os.environ:
        raise Exception("PVOUTPUT_ID missing")
    else:
        pvoutput_id = os.environ['PVOUTPUT_ID']
    if 'PVOUTPUT_KEY' not in os.environ:
        raise Exception("PVOUTPUT_KEY missing")
    else:
        pvoutput_key = os.environ['PVOUTPUT_KEY']

    log.debug("Report weather info to pvoutput.org for %s", day)

    time_value = time.mktime(time.strptime("%s2100" % day, "%Y%m%d%H%M"))
    w = get_daytime_weather_data(log, time_value)

    short_description = "Not Sure"
    if "partly cloudy" in w["description"].lower():
        short_description = "Partly Cloudy"
    if "mostly cloudy" in w["description"].lower():
        short_description = "Mostly Cloudy"
    elif "snow" in w["description"].lower():
        short_description = "Snow"
    elif "rain" in w["description"].lower():
        short_description = "Showers"
    elif "clear" in w["description"].lower():
        short_description = "Fine"

    pvdata = {}
    pvdata["d"] = day
    pvdata["g"] = data["data"][day]["production"] * 1000
    pvdata["cd"] = short_description
    pvdata["tm"] = "%.1f" % ((w["low_temp"] - 32) * 5.0 / 9.0)
    pvdata["tx"] = "%.1f" % ((w["high_temp"] - 32) * 5.0 / 9.0)
    pvdata["cm"] = "Daylight hours: %.1f, Cloud cover: %d%%" % (data["data"][day]["daylight"],
                                                                data["data"][day]["cloud"])
    data = urllib.parse.urlencode(pvdata)

    headers = {}
    headers["X-Pvoutput-Apikey"] = pvoutput_key
    headers["X-Pvoutput-SystemId"] = pvoutput_id

    req = urllib.request.Request("http://pvoutput.org/service/r2/addoutput.jsp", data.encode('utf-8'), headers)
    response = urllib.request.urlopen(req)
    output = response.read()
    log.debug("   Upload response: %s", output)


def main():
    parser = argparse.ArgumentParser(description='SolarCity Reporting')
    parser.add_argument('--no_email', help='Dont send emails', required=False, action='store_true')
    parser.add_argument('--force', help='Force update', required=False, action='store_true')
    parser.add_argument('--no_tweet', help='Dont post tweets', required=False, action='store_true')
    parser.add_argument('--report', help='Generate report', required=False, action='store_true')
    parser.add_argument('--blog', help='Generate html report page', required=False, action='store_true')
    parser.add_argument('--daily', help='Report on daily generation', required=False, action='store_true')
    parser.add_argument('--monthly', help='Report on monthly generation', required=False, action='store_true')
    parser.add_argument('--yearly', help='Report on yearly generation', required=False, action='store_true')
    parser.add_argument('--weather', help='Report weather for given date (YYYYMMDD)', required=False, type=str)
    parser.add_argument('--pvoutput', help="Send data for date (YYYYMMDD) to PVOutput.org", required=False, type=str)
    args = parser.parse_args()

    # Make sure we only run one instance at a time
    fp = open('/tmp/solarcity.lock', 'w')
    try:
        fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
    except:
        log.debug("Sorry, someone else is running this tool right now. Please try again later")
        return -1

    log.debug("--- solarcity.py start ---")

    data = load_data()
    data_changed = False

    data = load_historical_data(data)
    production_max, production_min, total_generation = analyze_data(data)

    if args.monthly:
        # First check if its last day of the month
        log.debug("Check for monthly update")
        now = datetime.datetime.now()
        dow, last_day = calendar.monthrange(now.year, now.month)
        log.debug("Last day of month: %d. Current day: %d", last_day, now.day)
        if last_day == now.day:
            log.debug("   Last day of month.")
            current_month = time.strftime("%Y%m")
            if 'lastmonthlytweet' not in data['config'] or data['config']['lastmonthlytweet'] != current_month:
                tweet_month(data)
                data['config']['lastmonthlytweet'] = current_month
                data_changed = True
        else:
            log.debug("   Not last day of month, skipping. ")

    if args.yearly:
        # First check if its last day of the year
        log.debug("Check for annual update")
        now = datetime.datetime.now()
        if now.month == 12:
            dow, last_day = calendar.monthrange(now.year, now.month)
            log.debug("Last day of month: %d. Current day: %d", last_day, now.day)
            if last_day == now.day:
                log.debug("   Last day of year.")
                current_month = time.strftime("%Y%m")
                if 'lastyearlytweet' not in data['config'] or data['config']['lastyearlytweet'] != current_month:
                    tweet_year(data)
                    data['config']['lastyearlytweet'] = current_month
                    data_changed = True
            else:
                log.debug("   Not last day of year, skipping. ")

    if args.weather is not None:
        log.debug("Check weather data")
        if int(args.weather) == 0:
            time_value = int(time.time())
        else:
            time_value = time.mktime(time.strptime("%s2100" % args.weather, "%Y%m%d%H%M"))
        w = get_daytime_weather_data(log, time_value)
        print("Weather as of %s:" % datetime.datetime.fromtimestamp(time_value))
        print("   Average temperature: %.1fF" % w["avg_temp"])
        print("   Low temperature: %.1fF" % w["low_temp"])
        print("   Cloud Cover: %d%%" % w["cloud_cover"])
        print("   Daylight hours: %.1f" % w["daylight"])
        print("   Description: %s" % w["description"])
        print("   Precipitation type: %s" % w["precip_type"])
        print("   Precipitation Chance: %d%%" % w["precip_probability"])
        # analyze_weather(data)

    if args.pvoutput is not None:
        if int(args.pvoutput) == 0:
            print("Uploading historical data to pvoutput.org")
            for d in data["data"]:
                print("   Processing date %s" % d)
                try:
                    upload_to_pvoutput(data, d)
                except:
                    print("      problem with date %s" % d)
                print("      Sleeping")
                # You'll need longer sleeps if you didnt donate
                time.sleep(15)
        else:
            upload_to_pvoutput(data, args.pvoutput)

    if args.daily:
        log.debug("Check for daily update")
        current_day = time.strftime("%Y%m%d")
        if data['config']['lastdailytweet'] != current_day or DEBUG_MODE or args.force:
            daylight_hours, cloud_cover, production = get_current_day_data()
            data['data'][current_day] = {'daylight': daylight_hours, 'cloud': cloud_cover, 'production': production}
            special = None
            if production_max is None or production > data['data'][production_max]['production']:
                special = "high"
            elif production_min is None or production < data['data'][production_min]['production']:
                special = "low"
            if not args.no_tweet:
                tweet_production(daylight_hours, cloud_cover, production, special)
                data['config']['lastdailytweet'] = current_day
            data_changed = True
            if args.pvoutput is not None:
                # Now upload to pvoutput
                upload_to_pvoutput(data, current_day)

    if args.report:
        # Send/Run weekly solarcity summary report
        solarcity_report(data, args.no_email, args.no_tweet)

    if args.blog:
        # Export all entries found for posting to static page on blog: teslaliving.net/solarcity
        log.debug("Reporting on SolarCity generation for blog")
        print('<a href="http://share.solarcity.com/teslaliving">@SolarCity</a> Solar Installation')
        print('<h3>System Results</h3>')
        print("<b>%s total power generated via @SolarCity as of %s</b>" % (show_with_units(total_generation),
                                                                    time.strftime("%Y%m%d")))
        print("%s day max on %s" % (show_with_units(data['data'][production_max]['production']), production_max))
        print("%s day min on %s" % (show_with_units(data['data'][production_min]['production']), production_min))
        print("<b>%s daily average production</b>" % (show_with_units(total_generation / len(data['data']))))
        print('<h3>System Details</h3>')
        print("System size is 69 panels at 255W each = %.1fkW" % (69 * .255))
        r = relativedelta(datetime.datetime.now(), datetime.datetime.strptime("2015-02-23", '%Y-%m-%d'))
        elapsed_months = r.years * 12 + r.months
        print("System was turned on February 23, 2015 (%d months ago)" % elapsed_months)
        print("Panel info: ")
        print("* Size: 1638 x 982 x 40mm (64.5 x 38.7 x 1.57in)")
        print("* Vendor: <a href='http://www.canadiansolar.com/solar-panels/cs6p-p.html'>CanadianSolar CS6P-P</a>")
        print("Inverter info: ")
        print("* <a href='http://www.solaredge.com/sites/default/files/se-single-phase-us-inverter-datasheet.pdf'>SolarEdge SE6000A</a>")
        print(" ")
        print('Sign up for <a href="http://share.solarcity.com/teslaliving">SolarCity</a> and save on electric!')

        print('<h3>Chart via <a href="http://pvoutput.org/list.jsp?id=48753&sid=44393">PVOutput</a></h3>[hoops name="pvoutput"]')
        print('<h3>Daily Log:</h3>')
        print("%s%s%s&nbsp;&nbsp;%s&nbsp;&nbsp;%s" % ("Date", "&nbsp;" * 11, "Production", "Daylight", "Cloud Cover"))
        d = data['data']
        for e in sorted(d, reverse=True):
            production = d[e]['production']
            if 'daylight' in d[e] and d[e]['daylight'] > 0:
                daylight = d[e]['daylight']
                if 'cloud' in d[e]:
                    cloud = d[e]['cloud']
                else:
                    cloud = 0
            else:
                w = get_daytime_weather_data(log, time.mktime(time.strptime("%s2100" % e, "%Y%m%d%H%M")))
                d[e]['daylight'] = w['daylight']
                daylight = w['daylight']
                d[e]['weather_api'] = True
                d[e]['cloud'] = w['cloud_cover']
                cloud = w['cloud_cover']
                d[e]['weather_api'] = True
                data_changed = True

            if production is not None and daylight is not None and cloud is not None:
                print('%s' % e, '&nbsp;&nbsp;&nbsp;&nbsp;%s&nbsp;%.1f hrs&nbsp;%d%%' % \
                                (show_with_units(production), daylight, cloud))
            else:
                print('%s' % e, '&nbsp;&nbsp;&nbsp;&nbsp;%s' % show_with_units(production))

        print('\nSign up for <a href="http://share.solarcity.com/teslaliving">SolarCity</a> and save on electric!')
        print('\nFollow <a href="https://twitter.com/teslaliving">@TeslaLiving</a>.')
        print('\n<ul>')
        print('<li><i>Note 1: Detailed generation tracking started 20150612.</i></li>')
        print('<li><i>Note 2: Cloud/Daylight data <a href="http://forecast.io">Powered by Forecast</a> when ' \
              'SolarCity data missing.</i></li>')
        print('<li><i>Note 3: System was degraded from 20170530 to 20170726. Up to 30 panels offline.</i></li>')
        print('</ul>')

    if data_changed:
        save_data(data)

    log.debug("--- solarcity.py end ---")


if __name__ == '__main__':
    try:
        main()
    except SystemExit:
        pass
    except:
        log.exception("Exception encountered")
        message = "There was a problem during solarcity updates:\n\n"
        message += traceback.format_exc()
        message += "\nPlease investigate."
        if DEBUG_MODE:
            raise
        else:
            email(email=SOLARCITY_USER, message=message, subject="Solarcity Poll Error")
