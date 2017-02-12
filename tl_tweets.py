#!/usr/bin/env python
# encoding: utf-8
"""
tl_tweets.py

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
Twitter Helper Functions

Dependencies: twython: https://github.com/ryanmcgrath/twython

You need to get application keys for Twitter at https://apps.twitter.com

Provide them via environment variables:
    TL_APP_KEY
    TL_APP_SECRET
    TL_OAUTH_TOKEN
    TL_OAUTH_TOKEN_SECRET

Or via init function.

Note: The logging stuff is as Twython emits a bunch of stuff during its work that I wanted to suppress
"""

import os
import sys
import time
import random
import logging
import sys

basepath = os.path.dirname(sys.argv[0])
sys.path.append(os.path.join(basepath, 'twython'))
from twython import Twython, TwythonAuthError


# Initialize Twitter Keys
APP_KEY = None
APP_SECRET = None
OAUTH_TOKEN = None
OAUTH_TOKEN_SECRET = None

# Cache self ID
MYSELF = None

if 'TL_APP_KEY' in os.environ:
    APP_KEY = os.environ['TL_APP_KEY']

if 'TL_APP_SECRET' in os.environ:
    APP_SECRET = os.environ['TL_APP_SECRET']

if 'TL_OAUTH_TOKEN' in os.environ:
    OAUTH_TOKEN = os.environ['TL_OAUTH_TOKEN']

if 'TL_OAUTH_TOKEN_SECRET' in os.environ:
    OAUTH_TOKEN_SECRET = os.environ['TL_OAUTH_TOKEN_SECRET']


def init_twitter_account(app_key, app_secret, oauth_token, oauth_token_secret):
    global APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET, MYSELF
    APP_KEY = app_key
    APP_SECRET = app_secret
    OAUTH_TOKEN = oauth_token
    OAUTH_TOKEN_SECRET = oauth_token_secret
    MYSELF = None


def check_twitter_config():
    if not APP_KEY:
        raise Exception("APP_KEY missing for twitter")
    if not APP_SECRET:
        raise Exception("APP_KEY missing for twitter")
    if not OAUTH_TOKEN:
        raise Exception("OAUTH_TOKEN missing for twitter")
    if not OAUTH_TOKEN_SECRET:
        raise Exception("OAUTH_TOKEN_SECRET missing for twitter")


def twitter_auth_issue(e):
    message = "There was a problem with automated tweet operations:\n\n"
    message += e
    message += "\nPlease investigate."
    print >> sys.stderr, message


def tweet_string(message, log, media=None):
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()

    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)

    retries = 0
    while retries < 5:
        log.setLevel(logging.ERROR)
        try:
            if media:
                photo = open(media, 'rb')
                media_ids = twitter.upload_media(media=photo)
                twitter.update_status(status=message.encode('utf-8').strip(), media_ids=media_ids['media_id'])
            else:
                twitter.update_status(status=message.encode('utf-8').strip())
            break
        except TwythonAuthError, e:
            log.setLevel(old_level)
            log.exception("   Problem trying to tweet string")
            twitter_auth_issue(e)
            return
        except:
            log.setLevel(old_level)
            log.exception("   Problem trying to tweet string")
        retries += 1
        s = random.randrange(5, 10 * retries)
        log.debug("   sleeping %d seconds for retry", s)
        time.sleep(s)

    log.setLevel(old_level)
    if retries == 5:
        log.error("Couldn't tweet string: %s with media: %s", message, media)


def tweet_price(price, log, stock, extra="", image=None):
    log.debug("      Tweet about stock price for %s: $%s", stock, price)
    message = "$%s current stock price: $%s. %s #bot" % (stock, price, extra)
    tweet_string(message=message, log=log, media=image)


def tweet_search(log, item, limit=50):
    log.debug("   Searching twitter for %s", item)
    check_twitter_config()
    if len(item) > 500:
        log.error("      Search string too long")
        raise Exception("Search string too long: %d", len(item))
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    try:
        result = twitter.search(q=item, count=limit)
    except TwythonAuthError, e:
        twitter_auth_issue(e)
        raise
    except:
        raise
    log.setLevel(old_level)
    return result


def check_relationship(log, id):
    my_screen_name = get_screen_name(log)
    if my_screen_name == "Unknown":
        raise("Couldn't get my own screen name")
    log.debug("      Checking relationship of %s with me (%s)", id, my_screen_name)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    try:
        result = twitter.show_friendship(source_screen_name=my_screen_name, target_screen_name=id)
    except TwythonAuthError, e:
        log.setLevel(old_level)
        log.exception("   Problem trying to check relationship")
        twitter_auth_issue(e)
        raise
    except:
        raise
    log.setLevel(old_level)
    return result["relationship"]["source"]["following"], result["relationship"]["source"]["followed_by"]


def follow_twitter_user(log, id):
    log.debug("   Following %s", id)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    try:
        twitter.create_friendship(screen_name=id)
    except TwythonAuthError, e:
        log.setLevel(old_level)
        log.exception("   Problem trying to follow twitter user")
        twitter_auth_issue(e)
        raise
    except:
        raise
    log.setLevel(old_level)


def unfollow_twitter_user(log, id):
    log.debug("   Unfollowing %s", id)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    try:
        twitter.destroy_friendship(screen_name=id)
    except TwythonAuthError, e:
        log.setLevel(old_level)
        log.exception("Error unfollowing %s", id)
        twitter_auth_issue(e)
        raise
    except:
        log.exception("Error unfollowing %s", id)
    log.setLevel(old_level)


def get_account_details(log, id):
    log.debug("   Getting account details for %s", id)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    try:
        details = twitter.show_user(screen_name=id)
    except TwythonAuthError, e:
        log.setLevel(old_level)
        log.exception("   Problem trying to get account details")
        twitter_auth_issue(e)
        raise
    except:
        details = None
    log.setLevel(old_level)
    return details


def get_follower_count(log, id):
    log.debug("   Getting follower count for %s", id)
    details = get_account_details(log, id)
    if details:
        log.debug("    %d", details["followers_count"])
        return details["followers_count"]
    else:
        return None


def get_screen_name(log):
    global MYSELF
    if not MYSELF or MYSELF == "Unknown":
        log.debug("   Getting current user screen name")
        check_twitter_config()
        logging.captureWarnings(True)
        old_level = log.getEffectiveLevel()
        log.setLevel(logging.ERROR)
        twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
        try:
            details = twitter.verify_credentials()
        except TwythonAuthError, e:
            log.setLevel(old_level)
            log.exception("   Problem trying to get screen name")
            twitter_auth_issue(e)
            raise
        except:
            log.exception("   Problem trying to get screen name")
            details = None
        log.setLevel(old_level)
        name = "Unknown"
        if details:
            name = details["screen_name"]
        MYSELF = name
    return MYSELF


def get_following(log, id):
    log.debug("  Getting people %s is following", id)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    log.setLevel(old_level)

    cursor = -1
    max_loops = 15
    while cursor != 0:
        try:
            log.setLevel(logging.ERROR)
            following = twitter.get_friends_list(screen_name=id, cursor=cursor, count=200)
            log.setLevel(old_level)
        except TwythonAuthError, e:
            log.exception("   Problem trying to get people following")
            twitter_auth_issue(e)
            raise
        except:
            raise
        for u in following["users"]:
            yield u["screen_name"]
        cursor = following["next_cursor"]
        if cursor:
            s = random.randint(55, 65)
            log.debug("      Sleeping %ds to avoid rate limit. Cursor: %s", s, cursor)
            time.sleep(s)
        else:
            log.debug("      Normal query end")

        max_loops -= 1
        if max_loops <= 0:
            log.debug("      Killing search due to max loops")
            break
    log.setLevel(old_level)


def get_followers(log, id):
    log.debug("  Getting people following % s", id)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    log.setLevel(old_level)

    cursor = -1
    max_loops = 15
    while cursor != 0:
        try:
            log.setLevel(logging.ERROR)
            following = twitter.get_followers_list(screen_name=id, cursor=cursor, count=200)
            log.setLevel(old_level)
        except TwythonAuthError, e:
            log.exception("   Problem trying to get people following")
            twitter_auth_issue(e)
            raise
        except:
            raise
        for u in following["users"]:
            yield u
        cursor = following["next_cursor"]
        if cursor:
            s = random.randint(55, 65)
            log.debug("      Sleeping %ds to avoid rate limit. Cursor: %s", s, cursor)
            time.sleep(s)
        else:
            log.debug("      Normal query end")

        max_loops -= 1
        if max_loops <= 0:
            log.debug("      Killing search due to max loops")
            break
    log.setLevel(old_level)
