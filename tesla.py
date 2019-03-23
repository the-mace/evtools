#!/usr/bin/env python
# encoding: utf-8
"""
tesla.py

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

Monitor your Tesla via the unofficial Tesla API

Supply your myTesla login information via environment variables:
    TESLA_EMAIL
    TESLA_PASSWORD

Uses third party library:
    https://github.com/gglockner/teslajson

See also the unofficial Tesla API docs:
    http://docs.timdorr.apiary.io/#

Examples:
    ./tesla.py --pluggedin - Check if your Tesla is plugged in

I use cron to run a bunch of these, example:
00     22        *       *       * source ~/.bashrc;cd "~/Documents/Data";/usr/bin/python \
                                                        ~/Documents/Code/evtools/tesla.py --pluggedin

Use --help for all options
"""

import os
import json
import argparse
import fcntl
import logging
from logging.handlers import RotatingFileHandler
import traceback
import time
import random
from urllib.error import HTTPError
import datetime
from tl_tweets import tweet_string
from tl_email import email
from tl_weather import get_daytime_weather_data
import glob

import sys
basepath = os.path.dirname(sys.argv[0])
sys.path.append(os.path.join(basepath, 'teslajson'))
import teslajson


# Where logging output from this tool goes. Modify path as needed
LOGFILE = os.path.expanduser(os.environ['TESLA_LOGFILE'])

# Data file containing all the saved state information
DATA_FILE = os.path.expanduser(os.getenv('TESLA_DATA_FILE', "tesla.json"))

# Subdirectory where Tesla state dumps will be saved
DUMP_DIR = "tesla_state_dumps"

# Updated with your car name (API needs car name)
CAR_NAME = os.environ['TESLA_CAR_NAME']

# Some of the tweets attach pictures. They're randomly chosen from this path
PICTURES_PATH = os.path.expanduser(os.getenv('TESLA_PICTURES_PATH', "images/favorites"))
VERSION_IMAGES = glob.glob('images/versions/*-watermark*')

# Logging setup
DEF_FRMT = "%(asctime)s : %(levelname)-8s : %(funcName)-25s:%(lineno)-4s: %(message)s"
loglevel = logging.DEBUG
logT = logging.getLogger("tesla")
loghandler = RotatingFileHandler(LOGFILE, maxBytes=5 * 1024 * 1024, backupCount=8)
loghandler.setFormatter(logging.Formatter(DEF_FRMT))
logT.addHandler(loghandler)
logT.setLevel(loglevel)

# Get the collection of pictures
def get_pics():
    if os.path.exists(PICTURES_PATH):
        pics = [os.path.join(PICTURES_PATH, f) for f in os.listdir(PICTURES_PATH) if not f.startswith('.')]
    else:
        pics = [None, ]
    return pics


# Set to true to disable tweets/data file updates
DEBUG_MODE = 'DEBUG_MODE' in os.environ
MAX_RETRIES = 3
RETRY_SLEEP = 10

# Get Teslamotors.com login information from environment
TESLA_EMAIL = None
TESLA_PASSWORD = None

if 'TESLA_EMAIL' in os.environ:
    TESLA_EMAIL = os.environ['TESLA_EMAIL']

if 'TESLA_PASSWORD' in os.environ:
    TESLA_PASSWORD = os.environ['TESLA_PASSWORD']

if not TESLA_EMAIL or not TESLA_PASSWORD:
    raise Exception("Missing Tesla login information")


def mail_exception(e):
    logT.exception("Exception encountered")
    message = "There was a problem during tesla updates:\n\n"
    message += e
    message += "\nPlease investigate."
    if DEBUG_MODE:
        raise Exception("email issues")
    else:
        email(email=TESLA_EMAIL, message=message, subject="Tesla script error")


def establish_connection(token=None):
    logT.debug("Connecting to Tesla")
    c = teslajson.Connection(email=TESLA_EMAIL, password=TESLA_PASSWORD, access_token=token)
    logT.debug("   connected. Token: %s", c.access_token)
    return c


def tweet_major_mileage(miles, get_tweet=False):
    m = "{:,}".format(miles)
    a = random.choice(["an amazing", "an awesome", "a fantastic", "a wonderful"])
    message = "Just passed %s miles on my Model S 75D! It's been %s experience. " \
              "#Tesla @TeslaMotors @Teslarati #bot" % (m, a)
    pic = random.choice(get_pics())
    if DEBUG_MODE:
        print("Would tweet:\n%s with pic: %s" % (message, pic))
        logT.debug("DEBUG mode, not tweeting: %s with pic: %s", message, pic)
    else:
        logT.info("Tweeting: %s with pic: %s", message, pic)
        if get_tweet:
            return message, pic
        else:
            tweet_string(message=message, log=logT, media=pic)


def dump_current_tesla_status(c):
    vehicles = c.vehicles
    m = ""
    for v in vehicles:
        m += "%s status at %s\n" % (v["display_name"], datetime.datetime.today())
        for i in v:
            if i != 'display_name':
                m += "   %s: %s\n" % (i, v[i])
        for s in ["vehicle_state", "charge_state", "climate_state", "drive_state", "gui_settings"]:
            m += "   %s:\n" % s
            d = v.data_request("%s" % s)
            for i in d:
                m += "      %s: %s\n" % (i, d[i])
    return m


def check_tesla_fields(c, data):
    data_changed = False
    new_fields = []

    t = datetime.date.today()
    ts = t.strftime("%Y%m%d")

    if not "known_fields" in data:
        data["known_fields"] = {}
        data_changed = True

    vehicles = c.vehicles
    for v in vehicles:
        logT.debug("   Processing %s" % v["display_name"])
        for i in v:
            if i not in data["known_fields"]:
                logT.debug("      found new field %s. Value: %s", i, v[i])
                new_fields.append(i)
                data["known_fields"][i] = ts
                data_changed = True
        for s in ["vehicle_state", "charge_state", "climate_state", "drive_state", "gui_settings"]:
            logT.debug("   Checking %s" % s)
            d = v.data_request("%s" % s)
            for i in d:
                if i not in data["known_fields"]:
                    logT.debug("      found new field %s. Value: %s", i, d[i])
                    new_fields.append(i)
                    data["known_fields"][i] = ts
                    data_changed = True

    if len(new_fields) > 0:
        m = "Found %s new Tesla API fields:\n" % "{:,}".format(len(new_fields))
        for i in new_fields:
            m += "\t%s\n" % i
        m += "\nRegards,\nRob"
        email(email=TESLA_EMAIL, message=m, subject="New Tesla API fields detected")
    else:
        logT.debug("   No new API fields detected.")
    return data_changed, data


def get_temps(c, car):
    inside_temp = None
    outside_temp = None
    for v in c.vehicles:
        if v["display_name"] == car:
            res = v.command("auto_conditioning_start")
            logT.debug("AC start: %s", res)
            time.sleep(5)
            d = v.data_request("climate_state")
            logT.debug("Climate: %s", d)
            inside_temp = 9.0 / 5.0 * d["inside_temp"] + 32
            outside_temp = 9.0 / 5.0 * d["outside_temp"] + 32
            res = v.command("auto_conditioning_stop")
            logT.debug("AC stop: %s", res)
    return inside_temp, outside_temp


def trigger_garage_door(c, car):
    logT.debug("Triggering garage door for %s", car)
    for v in c.vehicles:
        if v["display_name"] == car:
            res = v.command("trigger_homelink")
            logT.debug("Garage door trigger: %s", res)
    return


def trigger_sunroof(c, car, state):
    logT.debug("Setting sunroof to %s for %s", state, car)
    for v in c.vehicles:
        if v["display_name"] == car:
            cmd = {"state": state}
            res = v.command("sun_roof_control", data=cmd)
            logT.debug("Garage door trigger: %s", res)
    return


def get_odometer(c, car):
    odometer = None
    for v in c.vehicles:
        if v["display_name"] == car:
            d = v.data_request("vehicle_state")
            odometer = int(d["odometer"])
    logT.debug("Mileage: %s", "{:,}".format(int(odometer)))
    return odometer


def is_plugged_in(c, car):
    plugged_in = False
    for v in c.vehicles:
        if v["display_name"] == car:
            d = v.data_request("charge_state")
            # charge_port_door_open and charge_port_latch have been unreliable individually
            charge_door_open = d["charge_port_latch"] == "Disengaged" or d["charge_port_door_open"]
            state = d["charging_state"]
            plugged_in = charge_door_open and state != "Disconnected"
            logT.debug("Door unlatched: %s. State: %s", charge_door_open, state)
            logT.debug("Latch: %s Door open: %s", d["charge_port_latch"], d["charge_port_door_open"])
    return plugged_in


def is_charging(c, car):
    rc = False
    for v in c.vehicles:
        if v["display_name"] == car:
            d = v.data_request("charge_state")
            logT.debug("   Charging State: %s", d["charging_state"])
            state = d["charging_state"]
            if state == "Charging" or state == "Complete":
                rc = True
    return rc

def get_current_state(c, car, include_temps=False):
    s = {}
    for v in c.vehicles:
        if v["display_name"] == car:
            d = v.data_request("vehicle_state")
            s["odometer"] = d["odometer"]
            s["version"] = d["car_version"]
            if include_temps:
                s["inside_temp"], s["outside_temp"] = get_temps(c, car)
            d = v.data_request("charge_state")
            s["soc"] = d["battery_level"]
            s["ideal_range"] = d["ideal_battery_range"]
            s["rated_range"] = d["battery_range"]
            s["estimated_range"] = d["est_battery_range"]
            s["charge_energy_added"] = d["charge_energy_added"]
            s["charge_miles_added_ideal"] = d["charge_miles_added_ideal"]
            s["charge_miles_added_rated"] = d["charge_miles_added_rated"]
            logT.debug(s)
            return s


def load_data():
    if os.path.exists(DATA_FILE):
        logT.debug("Loading existing tesla database")
        data = json.load(open(DATA_FILE, "r"))
        logT.debug("  loaded")
    else:
        logT.debug("No existing tesla database found")
        data = {'daily_state': {}}
    if not 'daily_state_pm' in data:
        data['daily_state_pm'] = {}
    if not 'daily_state_am' in data:
        data['daily_state_am'] = {}
    if 'config' in data:
        del data['config']
    if "day_charges" not in data:
        data["day_charges"] = 0
    if "charging" not in data:
        data["charging"] = False
    return data


def save_data(data):
    logT.debug("Save tesla database")
    if not DEBUG_MODE:
        json.dump(data, open(DATA_FILE + ".tmp", "w"))
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        os.rename(DATA_FILE + ".tmp", DATA_FILE)
    else:
        logT.debug("   Skipped saving due to debug mode")


def get_lock():
    # Make sure we only run one instance at a time
    blocked = True
    max_wait_count = 10
    while blocked:
        fp = open('/tmp/tesla.lock', 'w')
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            blocked = False
        except:
            max_wait_count -= 1
            if max_wait_count == 0:
                raise Exception("Lock file not getting released. Please investigate")
            logT.debug("Someone else is running this tool right now. Sleeping")
            time.sleep(30)


def remove_lock():
    try:
        os.remove('/tmp/tesla.lock')
    except:
        pass


def report_yesterday(data):
    # Report on yesterdays mileage/efficiency
    t = datetime.date.today()
    today_ts = t.strftime("%Y%m%d")
    t = t + datetime.timedelta(days=-1)
    yesterday_ts = t.strftime("%Y%m%d")
    if today_ts not in data["daily_state_am"] or yesterday_ts not in data["daily_state_am"]:
        logT.debug("Skipping yesterday tweet due to missing items")
        m = None
        pic = None
    else:
        miles_driven = data["daily_state_am"][today_ts]["odometer"] - data["daily_state_am"][yesterday_ts][
            "odometer"]
        kw_used = data["daily_state_am"][today_ts]["charge_energy_added"]
        if miles_driven > 200:
            m = "Yesterday I drove my #Tesla %s miles on a road trip! " \
                "@Teslamotors #bot" % ("{:,}".format(int(miles_driven)))
        elif miles_driven == 0:
            mileage = data["daily_state_am"][today_ts]["odometer"]
            today_ym = datetime.date.today()
            start_ym = datetime.date(2014, 4, 21)
            ownership_months = int((today_ym - start_ym).days / 30)
            m = "Yesterday my #Tesla had a day off. Current mileage is %s miles after %d months " \
                "@Teslamotors #bot" % ("{:,}".format(int(mileage)), ownership_months)
        elif data["day_charges"] == 0 or data["day_charges"] > 1:
            # Need to skip efficiency stuff here if car didnt charge last night or we charged more than once
            # TODO: Could save prior efficiency from last charge and use that
            day = yesterday_ts
            time_value = time.mktime(time.strptime("%s2100" % day, "%Y%m%d%H%M"))
            w = get_daytime_weather_data(logT, time_value)
            m = "Yesterday I drove my #Tesla %s miles. Avg temp %.0fF. " \
                "@Teslamotors #bot" \
                % ("{:,}".format(int(miles_driven)), w["avg_temp"])
        else:
            # Drove a distance and charged exactly once since last report, we have enough data
            # to report efficiency.
            day = yesterday_ts
            time_value = time.mktime(time.strptime("%s2100" % day, "%Y%m%d%H%M"))
            w = get_daytime_weather_data(logT, time_value)
            efficiency = kw_used * 1000 / miles_driven
            # If efficiency isnt a reasonable number then don't report it.
            # Example, drive somewhere and don't charge -- efficiency is zero.
            # Or drive somewhere, charge at SC, then do normal charge - efficiency will look too high.
            if kw_used > 0 and efficiency > 200 and efficiency < 700:
                m = "Yesterday I drove my #Tesla %s miles using %.1f kWh with an effic. of %d Wh/mi. Avg temp %.0fF. " \
                    "@Teslamotors #bot" \
                    % ("{:,}".format(int(miles_driven)), kw_used, efficiency, w["avg_temp"])
            else:
                m = "Yesterday I drove my #Tesla %s miles. Avg temp %.0fF. " \
                    "@Teslamotors #bot" % ("{:,}".format(int(miles_driven)), w["avg_temp"])
        pic = os.path.abspath(random.choice(get_pics()))
    return m, pic


def get_update_for_yesterday():
    get_lock()
    data = load_data()
    m, pic = report_yesterday(data)
    remove_lock()
    return m, pic


def check_current_firmware_version(c, data):
    v = None
    changed = False
    try:
        v = c.vehicles[0].data_request("vehicle_state")["car_version"].split(" ")[0]
        logT.debug("Found firmware version %s", v)
    except:
        logT.warning("Problems getting firmware version")

    t = datetime.date.today()
    ts = t.strftime("%Y%m%d")

    if "firmware" in data:
        if data["firmware"]["version"] != v:
            # TODO: Log new one found
            data["firmware"]["version"] = v
            data["firmware"]["date_detected"] = ts
            changed = True
        else:
            last_date = time.strptime(data["firmware"]["date_detected"], "%Y%m%d")
            last_date = datetime.date.fromtimestamp(time.mktime(last_date))
            time_since = (datetime.date.today() - last_date).days

            firmware_date = time.strptime(v[:7]+".6", "%Y.%W.%w")
            firmware_age = (datetime.date.today() - datetime.date.fromtimestamp(time.mktime(firmware_date))).days

            message = "My 2018 S75D is running firmware version %s. " \
                      "Firmware is ~%d days old. " \
                      "%d days since last update #bot" % (v, firmware_age, time_since)
            pic = random.choice(VERSION_IMAGES)
            if DEBUG_MODE:
                print("Would tweet:\n%s with pic: %s" % (message, pic))
                logT.debug("DEBUG mode, not tweeting: %s with pic: %s", message, pic)
            else:
                logT.info("Tweeting: %s with pic: %s", message, pic)
                tweet_string(message=message, log=logT, media=pic)
    else:
        data["firmware"] = {}
        data["firmware"]["version"] = v
        data["firmware"]["date_detected"] = ts
        changed = True
    return changed


def main():
    parser = argparse.ArgumentParser(description='Tesla Control')
    parser.add_argument('--status', help='Get car status', required=False, action='store_true')
    parser.add_argument('--mileage', help='Check car mileage and tweet as it crosses 1,000 mile marks',
                        required=False, action='store_true')
    parser.add_argument('--state', help='Record car state', required=False, action='store_true')
    parser.add_argument('--pluggedin', help='Check if car is plugged in', required=False, action='store_true')
    parser.add_argument('--dump', help='Dump all fields/data', required=False, action='store_true')
    parser.add_argument('--fields', help='Check for newly added API fields', required=False, action='store_true')
    parser.add_argument('--day', help='Show state data for given day', required=False, type=str)
    parser.add_argument('--yesterday', help='Report on yesterdays driving', required=False, action='store_true')
    parser.add_argument('--export', help='Export data', required=False, action='store_true')
    parser.add_argument('--report', help='Produce summary report', required=False, action='store_true')
    parser.add_argument('--garage', help='Trigger garage door (experimental)', required=False, action='store_true')
    parser.add_argument('--sunroof', help='Control sunroof (vent, open, close)', required=False, type=str)
    parser.add_argument('--mailtest', help='Test emailing', required=False, action='store_true')
    parser.add_argument('--chargecheck', help='Check if car is currently charging', required=False,
                        action='store_true')
    parser.add_argument('--firmware', help='Check for new firmware versions', required=False, action='store_true')
    args = parser.parse_args()

    get_lock()
    logT.debug("--- tesla.py start ---")

    data = load_data()
    data_changed = False

    # Get a connection to the car and manage access token
    if 'token' in data:
        token = data['token']
    else:
        token = None
    try:
        c = establish_connection(token)
    except:
        logT.debug("Problems establishing connection")
        c = establish_connection()

    if c.access_token:
        if not 'token' in data or data['token'] != c.access_token:
            data['token'] = c.access_token
            data_changed = True

    if args.status:
        # Dump current Tesla status
        try:
            print(dump_current_tesla_status(c))
        except:
            logT.warning("Couldn't dump status this pass")

    elif args.dump:
        # Dump all of Tesla API state information to disk
        logT.debug("Dumping current Tesla state")
        t = datetime.date.today()
        ts = t.strftime("%Y%m%d")
        try:
            m = dump_current_tesla_status(c)
            open(os.path.join(DUMP_DIR, "tesla_state_%s.txt" % ts), "w").write(m)
        except:
            logT.warning("Couldn't get dump this pass")

    elif args.fields:
        # Check for new Tesla API fields and report if any found
        logT.debug("Checking Tesla API fields")
        try:
            data_changed, data = check_tesla_fields(c, data)
        except:
            logT.warning("Couldn't check fields this pass")

    elif args.mileage:
        # Tweet mileage as it crosses 1,000 mile marks
        try:
            m = get_odometer(c, CAR_NAME)
        except:
            logT.warning("Couldn't get odometer this pass")
            return

        if "mileage_tweet" not in data:
            data["mileage_tweet"] = 0
        if int(m / 1000) > int(data["mileage_tweet"] / 1000):
            tweet_major_mileage(int(m / 1000) * 1000)
            data["mileage_tweet"] = m
            data_changed = True

    elif args.chargecheck:
        # Check for charges so we can correctly report daily efficiency
        try:
            m = is_charging(c, CAR_NAME)
        except:
            logT.warning("Couldn't get charge state this pass")
            return

        if not data["charging"] and m:
            logT.debug("   State change, not charging to charging")
            data["charging"] = True
            data["day_charges"] += 1
            data_changed = True
        elif data["charging"] and m is False:
            logT.debug("   State change from charging to not charging")
            data["charging"] = False
            data_changed = True

    elif args.state:
        # Save current Tesla state information
        logT.debug("Saving Tesla state")
        retries = 3
        s = None
        while retries > 0:
            try:
                s = get_current_state(c, CAR_NAME)
                break
            except:
                retries -= 1
                if retries > 0:
                    logT.exception("   Problem getting current state, sleeping and trying again")
                    time.sleep(30)
        if s is None:
            logT.error("   Could not fetch current state")
            raise Exception("Couldnt fetch Tesla state")
        logT.debug("   got current state")
        t = datetime.date.today()
        ts = t.strftime("%Y%m%d")
        hour = datetime.datetime.now().hour
        if hour < 12:
            ampm = "am"
        else:
            ampm = "pm"
        data["daily_state_%s" % ampm][ts] = s
        logT.debug("   added to database")
        data_changed = True

    elif args.day:
        # Show Tesla state information from a given day
        ts = args.day
        raw = ""
        if ts in data["daily_state_am"]:
            print("Data for %s am:" % ts)
            for i in ("odometer", "soc", "ideal_range", "rated_range", "estimated_range", "charge_energy_added",
                      "charge_miles_added_ideal", "charge_miles_added_rated"):
                print("%s: %s" % (i, data["daily_state_am"][ts][i]))
                raw += "%s\t" % data["daily_state_am"][ts][i]
            print("\nRaw: %s" % raw)

    elif args.report:
        # Show total and average energy added
        total_energy_added = 0
        for ts in data["daily_state_am"]:
            if ts < "20151030":
                continue
            total_energy_added += data["daily_state_am"][ts]["charge_energy_added"]
        print("Total Energy Added: %s kW" % "{:,.2f}".format(total_energy_added))
        print("Average Energy Added: %s kW" % "{:,.2f}".format((total_energy_added / len(data["daily_state_am"]))))

    elif args.export:
        # Export all saved Tesla state information
        for ts in sorted(data["daily_state_am"]):
            if ts < "20151030":
                continue
            print("%s," % ts, end=' ')
            for i in ("odometer", "soc", "ideal_range", "rated_range", "estimated_range", "charge_energy_added",
                      "charge_miles_added_ideal", "charge_miles_added_rated"):
                print("%s," % data["daily_state_am"][ts][i], end=' ')
            print("")

    elif args.pluggedin:
        # Check if the Tesla is plugged in and alert if not
        logT.debug("Checking if Tesla is plugged in")
        if not is_plugged_in(c, CAR_NAME):
            s = get_current_state(c, CAR_NAME, include_temps=False)
            message = "Your car is not plugged in.\n\n"
            message += "Current battery level is %d%%. (%d estimated miles)" % (s["soc"], int(s["estimated_range"]))
            message += "\n\nRegards,\nRob"
            email(email=TESLA_EMAIL, message=message, subject="Your Tesla isn't plugged in")
            logT.debug("   Not plugged in. Emailed notice.")
        else:
            logT.debug("   Its plugged in.")

    elif args.mailtest:
        # Test emailing
        logT.debug("Testing email function")
        message = "Email test from tool.\n\n"
        message += "If you're getting this its working."
        message += "\n\nRegards,\nRob"
        try:
            email(email=TESLA_EMAIL, message=message, subject="Tesla Email Test")
            logT.debug("   Successfully sent the mail.")
            print("Mail send passed.")
        except:
            logT.exception("Problem trying to send mail")
            print("Mail send failed, see log.")

    elif args.yesterday:
        m, pic = report_yesterday(data)
        data["day_charges"] = 0
        data_changed = True

        if m:
            if DEBUG_MODE:
                print("Would tweet:\n%s with pic: %s" % (m, pic))
                logT.debug("DEBUG mode, not tweeting: %s with pic: %s", m, pic)
            else:
                logT.info("Tweeting: %s with pic: %s", m, pic)
                tweet_string(message=m, log=logT, media=pic)
        else:
            logT.debug("No update, skipping yesterday report")

    elif args.garage:
        # Open garage door (experimental as I dont have an AP car)
        trigger_garage_door(c, CAR_NAME)

    elif args.firmware:
        # Check firmware version for a change
        data_changed = check_current_firmware_version(c, data)

    elif args.sunroof:
        # Change sunroof state
        trigger_sunroof(c, CAR_NAME, args.sunroof)

    if data_changed:
        save_data(data)

    remove_lock()
    logT.debug("--- tesla.py end ---")


if __name__ == '__main__':
    for retry in range(MAX_RETRIES):
        try:
            main()
            break
        except SystemExit:
            break
        except HTTPError as e:
            if e.code >= 500 or e.code == 408:
                logT.debug("Transient error from Tesla API: %d", e.code)
                logT.debug("Retrying again in %d seconds", RETRY_SLEEP)
                time.sleep(RETRY_SLEEP)

                # Unlock and retry
                remove_lock()
            else:
                if DEBUG_MODE:
                    raise
                else:
                    mail_exception(traceback.format_exc())
                break
        except:
            if DEBUG_MODE:
                raise
            else:
                mail_exception(traceback.format_exc())
            break
