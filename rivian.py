#!/usr/bin/env python
# encoding: utf-8
"""
rivian.py

Copyright (c) 2023 Rob Mason

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

Monitor your Rivian via the unofficial Rivian API

Uses library:
    https://github.com/the-mace/rivian-python-api

See also the unofficial Rivian API docs:
    https://github.com/kaedenbrinkman/rivian-api

Examples:
    ./rivian.py --pluggedin - Check if your Rivian is plugged in

I use cron to run a bunch of these, example:
00     22        *       *       * source ~/.bashrc;cd "~/Documents/Data";/usr/bin/python \
                                                        ~/Documents/Code/evtools/rivian.py --pluggedin

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
import pickle
import random
from urllib.error import HTTPError
import datetime
from tl_tweets import tweet_string
from tl_email import email
from tl_weather import get_daytime_weather_data
import glob
from pythonjsonlogger import jsonlogger
from rivian_api import *


# Where logging output from this tool goes. Modify path as needed
LOGFILE = os.path.expanduser(os.environ['RIVIAN_LOGFILE'])

log = logging.getLogger(__name__)
loglevel = logging.INFO
DEF_FRMT = "%(asctime)s : %(levelname)-8s : %(funcName)-25s:%(lineno)-4s: %(message)s"
loghandler1 = RotatingFileHandler(LOGFILE, maxBytes=5 * 1024 * 1024, backupCount=8)
loghandler2 = RotatingFileHandler(LOGFILE + '.json', maxBytes=5 * 1024 * 1024, backupCount=8)
loghandler1.setFormatter(logging.Formatter(DEF_FRMT))
loghandler2.setFormatter(jsonlogger.JsonFormatter())
log.addHandler(loghandler1)
log.addHandler(loghandler2)
log.setLevel(loglevel)

# Data file containing Rivian auth information (created by Rivian CLI)
PICKLE_FILE = 'rivian_auth.pickle'

# Data file containing all the saved state information
DATA_FILE = os.path.expanduser(os.getenv('RIVIAN_DATA_FILE', "rivian.json"))

# Data file containing all the saved state information
SLEEP_LOG_FILE = os.path.expanduser(os.getenv('RIVIAN_SLEEP_LOG_FILE', "rivian_sleep_log.csv"))

# Subdirectory where Rivian state dumps will be saved
DUMP_DIR = "rivian_state_dumps"

# Updated with your car name (API needs vehicle ID)
VEHICLE_ID = os.environ['RIVIAN_VEHICLE_ID']

# Some tweets attach pictures. They're randomly chosen from this path
PICTURES_PATH = os.path.expanduser(os.getenv('RIVIAN_PICTURES_PATH', "images/rivian"))
VERSION_IMAGES = glob.glob('images/rivian_versions/*')

# Set to true to disable tweets/data file updates
DEBUG_MODE = 'RIVIAN_DEBUG_MODE' in os.environ
MAX_RETRIES = 3
RETRY_SLEEP = 10


# Get the collection of pictures
def get_pics():
    if os.path.exists(PICTURES_PATH):
        pics = [os.path.join(PICTURES_PATH, f) for f in os.listdir(PICTURES_PATH) if not f.startswith('.')]
    else:
        pics = [None, ]
    return pics


if 'RIVIAN_EMAIL' in os.environ:
    RIVIAN_EMAIL = os.environ['RIVIAN_EMAIL']
else:
    RIVIAN_EMAIL = None


if not RIVIAN_EMAIL:
    raise Exception("Missing Rivian contact information, please set RIVIAN_EMAIL in your environment")


def mail_exception(e):
    log.exception("Exception encountered")
    message = "There was a problem during Rivian updates:\n\n"
    message += e
    message += "\nPlease investigate."
    if DEBUG_MODE:
        raise Exception("email issues")
    else:
        email(email=RIVIAN_EMAIL, message=message, subject="Rivian script error")


def restore_state(rivian):
    while True:
        try:
            rivian.create_csrf_token()
            break
        except Exception as e:
            time.sleep(5)

    if os.path.exists(PICKLE_FILE):
        with open(PICKLE_FILE, 'rb') as f:
            obj = pickle.load(f)
        rivian._access_token = obj['_access_token']
        rivian._refresh_token = obj['_refresh_token']
        rivian._user_session_token = obj['_user_session_token']
    else:
        raise Exception("Please ensure you have a valid Rivian auth file (from Rivian CLI) first")


def establish_connection():
    rivian = Rivian()
    restore_state(rivian)
    return rivian


def get_vehicle_state(rivian, minimal=False):
    response_json = rivian.get_vehicle_state(vehicle_id=VEHICLE_ID, minimal=minimal)
    return response_json['data']['vehicleState']


def is_awake(rivian):
    v = get_vehicle_state(rivian, minimal=True)
    return v['powerState']['value'] not in ('sleep', 'standby')


def get_vehicle_data(rivian):
    log.info("Getting vehicle data")
    vehicle_data = get_vehicle_state(rivian, minimal=False)
    return vehicle_data


def tweet_major_mileage(miles, get_tweet=False):
    m = "{:,}".format(miles)
    a = random.choice(["an amazing",
                       "an awesome",
                       "a fantastic",
                       "a great",
                       "a wonderful"])
    message = "Just passed %s miles on my Rivian R1T! It's been %s experience. " \
              "#Rivian #R1T @Rivian @TezLabApp #bot" % (m, a)
    pic = random.choice(get_pics())
    if DEBUG_MODE:
        print("Would tweet:\n%s with pic: %s" % (message, pic))
        log.info("DEBUG mode, not tweeting: %s with pic: %s", message, pic)
    else:
        log.info("Tweeting: %s with pic: %s", message, pic)
        if get_tweet:
            return message, pic
        else:
            tweet_string(message=message, log=log, media=pic)


def dump_current_rivian_status(rivian):
    state = get_vehicle_state(rivian)
    return state


def get_temps(rivian):
    v = get_vehicle_state(rivian)
    inside_temp = 9.0 / 5.0 * v["cabinClimateInteriorTemperature"]["value"] + 32
    return inside_temp


def get_odometer(rivian):
    vehicle_data = rivian.get_vehicle_state(vehicle_id=VEHICLE_ID, minimal=True)
    odometer = float(vehicle_data['data']['vehicleState']['vehicleMileage']['value']) / 1609.0
    if odometer:
        log.info(f"Mileage: {int(odometer):,}")
    return odometer


def is_plugged_in(rivian):
    plugged_in = False
    vehicle_data = get_vehicle_data(rivian)
    if vehicle_data['chargerStatus']['value'] in ('chrgr_sts_connected_charging',
                                                  'chrgr_sts_connected_no_chrg'):
        plugged_in = True
    log.info(f"Plugged in: {plugged_in}")
    return plugged_in


def is_charging(rivian):
    rc = False
    vehicle_data = get_vehicle_data(rivian)
    charging_state = vehicle_data['chargerState']['value']
    log.info(f"Charging State: {charging_state}")
    if charging_state == "charging_active" or charging_state == "charging_complete":
        rc = True
    return rc


def get_current_state(rivian, include_temps=False):
    vehicle_data = get_vehicle_data(rivian)
    s = {}
    s["odometer"] = vehicle_data['vehicleMileage']['value'] / 1609.0
    s["version"] = vehicle_data['otaCurrentVersion']['value']
    if include_temps:
        s["inside_temp"] = get_temps(rivian)
    s["soc"] = vehicle_data['batteryLevel']['value']
    s["estimated_range"] = vehicle_data['distanceToEmpty']['value']
    s["charging"] = vehicle_data["charge_state"]["charging_state"]
    log.debug(s)
    return s


def load_data():
    if os.path.exists(DATA_FILE):
        log.debug("Loading existing rivian database")
        data = json.load(open(DATA_FILE, "r"))
        log.debug("loaded")
    else:
        log.debug("No existing rivian database found")
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
    log.debug("Save rivian database")
    if not DEBUG_MODE:
        json.dump(data, open(DATA_FILE + ".tmp", "w"))
        if os.path.exists(DATA_FILE):
            os.remove(DATA_FILE)
        os.rename(DATA_FILE + ".tmp", DATA_FILE)
    else:
        log.debug("Skipped saving due to debug mode")


def get_lock():
    # Make sure we only run one instance at a time
    blocked = True
    max_wait_count = 10
    while blocked:
        fp = open('/tmp/rivian.lock', 'w')
        try:
            fcntl.flock(fp.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
            blocked = False
        except:
            max_wait_count -= 1
            if max_wait_count == 0:
                raise Exception("Lock file not getting released. Please investigate")
            log.debug("Someone else is running this tool right now. Sleeping")
            time.sleep(30)


def remove_lock():
    try:
        os.remove('/tmp/rivian.lock')
    except:
        pass


def sleep_check(rivian):
    vehicle_data = get_vehicle_data(rivian)
    s = {}
    s['state'] = vehicle_data['powerState']['value']
    s['timestamp'] = datetime.datetime.now()
    awake = vehicle_data['powerState']['value'] not in ('sleep', 'standby')
    s["soc"] = round(vehicle_data["batteryLevel"]["value"], 1)
    s["charging"] = vehicle_data["chargerStatus"]["value"] == 'chrgr_sts_connected_charging'
    s["rated_range"] = round(vehicle_data["distanceToEmpty"]["value"], 1)
    s["driving"] = "Driving" if vehicle_data["powerState"]["value"] in ("go", "reverse") else "Parked"
    if not awake:
        s["assumed_state"] = "Sleeping"
    elif s["charging"] != True:
        if s["driving"] == "Driving":
            s["assumed_state"] = "Driving"
        else:
            s["assumed_state"] = "Idle"
    else:
        # If its charging don't treat it as a poke we need to avoid doing again soon
        s["assumed_state"] = "Charging"

    log_h = open(SLEEP_LOG_FILE, "a")
    log_h.write(f"{datetime.datetime.now(datetime.timezone.utc).astimezone()},"
                f"{s['state']},"
                f"{s['soc'] if 'soc' in s else ''},"
                f"{s['rated_range'] if 'rated_range' in s else ''},"
                f"{s['charging'] if 'charging' in s else ''},"
                f"{s['assumed_state'] if 'assumed_state' in s else ''},"
                f"{s['driving'] if 'driving' in s else ''},"
                ","
                f"{s['timestamp']}"
                "\n")
    log.info(f"Sleep Poll: {s['assumed_state']}", extra=s)
    return s


def report_yesterday(data):
    # Report on yesterday's mileage/efficiency
    t = datetime.date.today()
    today_ts = t.strftime("%Y%m%d")
    t = t + datetime.timedelta(days=-1)
    yesterday_ts = t.strftime("%Y%m%d")
    try:
        miles_driven = 0
        if data["daily_state_am"][yesterday_ts]["odometer"] and data["daily_state_am"][today_ts]["odometer"]:
            miles_driven = data["daily_state_am"][today_ts]["odometer"] - \
                           data["daily_state_am"][yesterday_ts]["odometer"]
        if miles_driven == 0 or miles_driven > 2000 or miles_driven < 0:
            log.warning(f'Something wrong with mileage: {miles_driven} '
                        f'{data["daily_state_am"][today_ts]["odometer"]} '
                        f'{data["daily_state_am"][yesterday_ts]["odometer"]}')
            return None, None
        if miles_driven > 200:
            m = "Yesterday I drove my #Rivian %s miles on a road trip! " \
                "@Rivian #bot" % ("{:,}".format(int(miles_driven)))
        elif miles_driven == 0:
            mileage = data["daily_state_am"][today_ts]["odometer"]
            today_ym = datetime.date.today()
            start_ym = datetime.date(2023, 3, 16)
            ownership_months = int((today_ym - start_ym).days / 30)
            m = "Yesterday my #Rivian had a day off. Current mileage is %s miles after %d months " \
                "@Rivian #bot" % ("{:,}".format(int(mileage)), ownership_months)
        elif data["day_charges"] == 0 or data["day_charges"] > 1:
            # Need to skip efficiency stuff here if car didnt charge last night or we charged more than once
            # TODO: Could save prior efficiency from last charge and use that
            day = yesterday_ts
            time_value = time.mktime(time.strptime("%s2100" % day, "%Y%m%d%H%M"))
            w = get_daytime_weather_data(log, time_value)
            m = "Yesterday I drove my #Rivian %s miles. Avg temp %.0fF. " \
                "@Rivian #bot" \
                % ("{:,}".format(int(miles_driven)), w["avg_temp"])
        else:
            m = "Yesterday I drove my #Rivian %s miles. Avg temp %.0fF. " \
                "@Rivian #bot" % ("{:,}".format(int(miles_driven)), w["avg_temp"])
        pic = os.path.abspath(random.choice(get_pics()))
    except:
        m = None
        pic = None
    return m, pic


def get_update_for_yesterday():
    get_lock()
    data = load_data()
    m, pic = report_yesterday(data)
    remove_lock()
    return m, pic


def check_current_firmware_version(rivian, data):
    v = None
    changed = False
    try:
        vehicle_data = get_vehicle_data(rivian)
        v = vehicle_data["otaCurrentVersion"]["value"]
        log.info("Found firmware version %s", v)
    except:
        log.exception("Problems getting firmware version")
        return changed

    t = datetime.date.today()
    ts = t.strftime("%Y%m%d")

    if "firmware" in data:
        last_date = time.strptime(data["firmware"]["date_detected"], "%Y%m%d")
        last_date = datetime.date.fromtimestamp(time.mktime(last_date))
        time_since = (datetime.date.today() - last_date).days

        if data["firmware"]["version"] != v:
            data["firmware"]["version"] = v
            data["firmware"]["date_detected"] = ts
            changed = True

            message = "My 2023 Rivian R1T just found software version %s. " \
                      "Its been %d days since the last update #bot" % (v, time_since)
        else:
            message = "My 2023 Rivian R1T is running firmware version %s. " \
                      "%d days since last update #bot" % (v, time_since)
        pic = random.choice(VERSION_IMAGES)

        if DEBUG_MODE:
            print("Would tweet:\n%s with pic: %s" % (message, pic))
            log.info("DEBUG mode, not tweeting: %s with pic: %s", message, pic)
        else:
            log.info("Tweeting: %s with pic: %s", message, pic)
            tweet_string(message=message, log=log, media=pic)
    else:
        data["firmware"] = {}
        data["firmware"]["version"] = v
        data["firmware"]["date_detected"] = ts
        changed = True
    return changed


def main():
    parser = argparse.ArgumentParser(description='Rivian Info')
    parser.add_argument('--status', help='Get car status', required=False, action='store_true')
    parser.add_argument('--mileage', help='Check car mileage and tweet as it crosses 1,000 mile marks',
                        required=False, action='store_true')
    parser.add_argument('--state', help='Record car state', required=False, action='store_true')
    parser.add_argument('--pluggedin', help='Check if car is plugged in', required=False, action='store_true')
    parser.add_argument('--dump', help='Dump all fields/data', required=False, action='store_true')
    parser.add_argument('--day', help='Show state data for given day', required=False, type=str)
    parser.add_argument('--yesterday', help='Report on yesterdays driving', required=False, action='store_true')
    parser.add_argument('--export', help='Export data', required=False, action='store_true')
    parser.add_argument('--report', help='Produce summary report', required=False, action='store_true')
    parser.add_argument('--mailtest', help='Test emailing', required=False, action='store_true')
    parser.add_argument('--chargecheck', help='Check if car is currently charging', required=False,
                        action='store_true')
    parser.add_argument('--firmware', help='Check for new firmware versions', required=False, action='store_true')
    parser.add_argument('--sleepcheck', help='Monitor sleeping state of Tesla', required=False, action='store_true')
    args = parser.parse_args()

    get_lock()
    log.debug("--- Rivian.py start ---")

    data = load_data()
    data_changed = False

    # Get a connection to the car and manage access token
    try:
        rivian = establish_connection()
    except:
        log.debug("Problems establishing connection")
        rivian = establish_connection()

    if args.status:
        log.info("Get Status")
        # Dump current Rivian status
        try:
            print(dump_current_rivian_status(rivian))
        except Exception as e:
            log.info(f"Couldn't dump status this pass: {str(e)}")

    if args.dump:
        # Dump all of Rivian API state information to disk
        log.info("Dumping current Rivian state")
        t = datetime.date.today()
        ts = t.strftime("%Y%m%d")
        try:
            m = dump_current_rivian_status(rivian)
            open(os.path.join(DUMP_DIR, "rivian_state_%s.txt" % ts), "w").write(str(m))
        except Exception as e:
            log.info(f"Couldn't get dump this pass: {str(e)}")

    if args.mileage:
        # Tweet mileage as it crosses 1,000 mile marks
        log.info("Get mileage")
        m = None
        try:
            m = get_odometer(rivian)
            if m:
                if "mileage_tweet" not in data:
                    data["mileage_tweet"] = 0
                if int(m / 1000) > int(data["mileage_tweet"] / 1000):
                    tweet_major_mileage(int(m / 1000) * 1000)
                    data["mileage_tweet"] = m
                    data_changed = True
                t = datetime.date.today()
                today_ts = t.strftime("%Y%m%d")
                if today_ts in data["daily_state_am"] and \
                        'odometer' not in data["daily_state_am"][today_ts]:
                    # Backfill odometer for state if we get it another way
                    data["daily_state_am"][today_ts]['odometer'] = m
                    data_changed = True
        except Exception as e:
            log.info(f"Problems getting odometer: {str(e)}")
        if not m:
            log.info("Couldn't get odometer this pass")

    if args.chargecheck:
        # Check for charges so we can correctly report daily efficiency
        log.info("Check for charges")
        try:
            m = is_charging(rivian)
            if not data["charging"] and m:
                log.debug("State change, not charging to charging")
                data["charging"] = True
                data["day_charges"] += 1
                data_changed = True
            elif data["charging"] and m is False:
                log.debug("State change from charging to not charging")
                data["charging"] = False
                data_changed = True
        except Exception as e:
            log.info(f"Couldn't get charge state this pass: {str(e)}")

    if args.state:
        # Save current Rivian state information
        log.info("Saving Rivian state")
        retries = 3
        s = None
        while retries > 0:
            try:
                s = get_current_state(rivian)
                break
            except Exception as e:
                retries -= 1
                if retries > 0:
                    log.info(f"Problem getting current state, sleeping and trying again: {str(e)}")
                    time.sleep(30)
        if s is None:
            log.warning("   Could not fetch current state")

        log.info("Got current state")
        t = datetime.date.today()
        ts = t.strftime("%Y%m%d")
        hour = datetime.datetime.now().hour
        if hour < 12:
            ampm = "am"
        else:
            ampm = "pm"
        tod = "daily_state_%s" % ampm
        data[tod][ts] = s
        log.info(f"Added to database in {tod}:{ts}")
        data_changed = True

    if args.day:
        # Show Rivian state information from a given day
        log.info("Show day info")
        ts = args.day
        raw = ""
        if ts in data["daily_state_am"]:
            print("Data for %s am:" % ts)
            for i in ("odometer", "soc", "estimated_range"):
                print("%s: %s" % (i, data["daily_state_am"][ts][i]))
                raw += "%s\t" % data["daily_state_am"][ts][i]
            print("\nRaw: %s" % raw)

    if args.report:
        # Show total and average energy added
        log.info("Generate report")
        total_energy_added = 0
        for ts in data["daily_state_am"]:
            total_energy_added += data["daily_state_am"][ts]["charge_energy_added"]
        print("Total Energy Added: %s kW" % "{:,.2f}".format(total_energy_added))
        if len(data["daily_state_am"]):
            print("Average Energy Added: %s kW" % "{:,.2f}".format((total_energy_added / len(data["daily_state_am"]))))

    if args.export:
        # Export all saved Rivian state information
        log.info("Export state")
        for ts in sorted(data["daily_state_am"]):
            print("%s," % ts, end=' ')
            for i in ("odometer", "soc", "estimated_range",):
                print("%s," % data["daily_state_am"][ts][i], end=' ')
            print("")

    if args.pluggedin:
        # Check if the Rivian is plugged in and alert if not
        log.debug("Checking if Rivian is plugged in")
        try:
            plugged_in = is_plugged_in(rivian)
            if plugged_in is None:
                log.warning("Car sleeping and data, couldnt check plugged in state")
            elif not plugged_in:
                s = get_current_state(rivian, include_temps=False)
                message = "Your car is not plugged in.\n\n"
                if s["soc"]:
                    message += "Current battery level is %d%%. " \
                               "(%d estimated miles)" % (s["soc"], int(s["estimated_range"]))
                message += "\n\nRegards,\nRob"
                email(email=RIVIAN_EMAIL, message=message, subject="Your Rivian isn't plugged in")
                log.debug("Not plugged in. Emailed notice.")
            else:
                log.debug("Its plugged in.")
        except Exception as e:
            log.info(f"Problem checking plugged in state: {str(e)}")


    if args.mailtest:
        # Test emailing
        log.debug("Testing email function")
        message = "Email test from rivian evtool.\n\n"
        message += "If you're getting this its working."
        message += "\n\nRegards,\nRob"
        try:
            email(email=RIVIAN_EMAIL, message=message, subject="Rivian Email Test")
            log.debug("Successfully sent the mail.")
            print("Mail send passed.")
        except Exception as e:
            log.info(f"Problem trying to send mail: {str(e)}")
            print("Mail send failed, see log.")

    if args.yesterday:
        log.info("Show yesterday info")
        m, pic = report_yesterday(data)
        data["day_charges"] = 0
        data_changed = True

        if m:
            if DEBUG_MODE:
                print("Would tweet:\n%s with pic: %s" % (m, pic))
                log.debug("DEBUG mode, not tweeting: %s with pic: %s", m, pic)
            else:
                log.info("Tweeting: %s with pic: %s", m, pic)
                tweet_string(message=m, log=log, media=pic)
        else:
            log.debug("No update, skipping yesterday report")

    if args.sleepcheck:
        # Change sleeping state of tesla
        log.info("Checking sleep state")
        tries = 0
        while True:
            try:
                sleep_check(rivian)
                break
            except Exception as e:
                log.info(f"Error checking sleep state: {str(e)}")
                raise
                if tries >= 3:
                    break
                time.sleep(10)
                tries += 1

    if args.firmware:
        # Check firmware version for a change
        log.info("Check firmware")
        data_changed = check_current_firmware_version(rivian, data)

    if data_changed:
        save_data(data)

    remove_lock()
    log.debug("--- rivian.py end ---")


if __name__ == '__main__':
    for retry in range(MAX_RETRIES):
        try:
            main()
            break
        except SystemExit:
            break
        except HTTPError as e:
            if e.code >= 500 or e.code == 408:
                log.warning("Transient error from Rivian API: %d", e.code)
                log.info("Retrying again in %d seconds", RETRY_SLEEP)
                time.sleep(RETRY_SLEEP)

                # Unlock and retry
                remove_lock()
            else:
                if DEBUG_MODE:
                    raise
                else:
                    mail_exception(traceback.format_exc())
                break
        except Exception as e:
            if DEBUG_MODE:
                raise
            else:
                mail_exception(str(e))
            break
