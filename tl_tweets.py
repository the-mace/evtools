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

Dependencies:
twython: https://github.com/ryanmcgrath/twython (most twython things no longer work as of APIv2)
tweepy: https://github.com/tweepy/tweepy

You need to get application keys for Twitter at https://apps.twitter.com

Provide them via environment variables:
    TL_APP_KEY
    TL_APP_SECRET
    TL_OAUTH_TOKEN
    TL_OAUTH_TOKEN_SECRET
    TL_BEARER_TOKEN

Or via init function.

Note: The logging stuff is as Twython emits a bunch of stuff during its work that I wanted to suppress

NOTE: ONLY tweet_string HAS BEEN TESTING/IS WORKING WITH TWITTER API 2.0
"""

import os
import sys
import argparse
import glob
import time
import random
import logging
from twython import Twython, TwythonAuthError
import tweepy

basepath = os.path.dirname(sys.argv[0])
sys.path.append(os.path.join(basepath, 'twython'))


# Initialize Twitter Keys
APP_KEY = None
APP_SECRET = None
OAUTH_TOKEN = None
OAUTH_TOKEN_SECRET = None
BEARER_TOKEN = None

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

if 'TL_BEARER_TOKEN' in os.environ:
    BEARER_TOKEN = os.environ['TL_BEARER_TOKEN']


def init_twitter_account(app_key, app_secret, oauth_token, oauth_token_secret, bearer_token=None):
    global APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET, BEARER_TOKEN, MYSELF
    APP_KEY = app_key
    APP_SECRET = app_secret
    OAUTH_TOKEN = oauth_token
    OAUTH_TOKEN_SECRET = oauth_token_secret
    BEARER_TOKEN = bearer_token
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
    if not BEARER_TOKEN:
        raise Exception("BEARER_TOKEN missing for twitter")


def twitter_auth_issue(e):
    message = "There was a problem with automated tweet operations.\n\n"
    message += "\nPlease investigate."
    print(message, file=sys.stderr)


def tweet_string(message, log, media=None):
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()

    log.setLevel(logging.ERROR)
    api = tweepy.Client(
        bearer_token=BEARER_TOKEN,
        access_token=OAUTH_TOKEN,
        access_token_secret=OAUTH_TOKEN_SECRET,
        consumer_key=APP_KEY,
        consumer_secret=APP_SECRET
    )

    uploaded_media = None
    if media:
        auth = tweepy.OAuth1UserHandler(
            APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET
        )
        oldapi = tweepy.API(auth)
        uploaded_media = oldapi.media_upload(filename=media)

    retries = 0
    while retries < 2:
        log.setLevel(logging.ERROR)
        try:
            if uploaded_media:
                api.create_tweet(
                    text=message,
                    media_ids=[uploaded_media.media_id]
                )
            else:
                api.create_tweet(
                    text=message
                )
            break
        except Exception as e:
            log.setLevel(old_level)
            log.exception("   Problem trying to tweet string")
            twitter_auth_issue(e)
            return
        except:
            log.setLevel(old_level)
            log.exception("   Problem trying to tweet string")
        retries += 1
        s = random.randrange(5, 10 * retries)
        log.debug("sleeping %d seconds for retry", s)
        time.sleep(s)

    log.setLevel(old_level)
    if retries == 5:
        log.error("Couldn't tweet string: %s with media: %s", message, media)


def tweet_price(price, log, stock, extra="", image=None):
    log.debug("Tweet about stock price for %s: $%s", stock, price)
    message = "$%s current stock price: $%s. %s" % (stock, price, extra)
    tweet_string(message=message, log=log, media=image)


def tweet_search(log, item, limit=50, since_id=None):
    log.debug("Searching twitter for '%s'", item)
    check_twitter_config()
    if len(item) > 500:
        log.error("      Search string too long")
        raise Exception("Search string too long: %d", len(item))
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    try:
        result = twitter.search(q=item, count=limit, since_id=since_id)
    except TwythonAuthError as e:
        log.setLevel(old_level)
        twitter_auth_issue(e)
        raise
    except:
        log.setLevel(old_level)
        raise
    log.setLevel(old_level)
    return result


def check_relationship(log, id):
    my_screen_name = get_screen_name(log)
    if my_screen_name == "Unknown":
        raise("Couldn't get my own screen name")
    log.debug("Checking relationship of %s with me (%s)", id, my_screen_name)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    try:
        result = twitter.show_friendship(source_screen_name=my_screen_name, target_screen_name=id)
    except TwythonAuthError as e:
        log.setLevel(old_level)
        log.exception("   Problem trying to check relationship")
        twitter_auth_issue(e)
        raise
    except:
        raise
    log.setLevel(old_level)
    return result["relationship"]["source"]["following"], result["relationship"]["source"]["followed_by"]


def follow_twitter_user(log, id):
    log.debug("Following %s", id)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    try:
        twitter.create_friendship(screen_name=id)
    except TwythonAuthError as e:
        log.setLevel(old_level)
        log.exception("   Problem trying to follow twitter user")
        twitter_auth_issue(e)
        raise
    except:
        raise
    log.setLevel(old_level)


def unfollow_twitter_user(log, id):
    log.debug("Unfollowing %s", id)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    try:
        twitter.destroy_friendship(screen_name=id)
    except TwythonAuthError as e:
        log.setLevel(old_level)
        log.exception("Error unfollowing %s", id)
        twitter_auth_issue(e)
        raise
    except:
        log.exception("Error unfollowing %s", id)
    log.setLevel(old_level)


def get_account_details(log, id):
    log.debug("Getting account details for %s", id)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    api = tweepy.Client(
        bearer_token=BEARER_TOKEN,
        access_token=OAUTH_TOKEN,
        access_token_secret=OAUTH_TOKEN_SECRET,
        consumer_key=APP_KEY,
        consumer_secret=APP_SECRET
    )
    try:
        user = api.get_user(username=id, user_fields=['public_metrics', 'verified', 'description'])
        details = {
            'screen_name': user.data.username,
            'name': user.data.name,
            'description': getattr(user.data, 'description', None),
            'verified': getattr(user.data, 'verified', None),
            'followers_count': user.data.public_metrics.get('followers_count', 0),
            'friends_count': user.data.public_metrics.get('following_count', 0),
            'statuses_count': user.data.public_metrics.get('tweet_count', 0),
            'id': user.data.id
        }
    except tweepy.NotFound:
        log.setLevel(old_level)
        details = None
    except Exception as e:
        log.setLevel(old_level)
        raise e
    log.setLevel(old_level)
    return details


def get_self_details(log):
    log.debug("Getting authenticated user details")
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    api = tweepy.Client(
        bearer_token=BEARER_TOKEN,
        access_token=OAUTH_TOKEN,
        access_token_secret=OAUTH_TOKEN_SECRET,
        consumer_key=APP_KEY,
        consumer_secret=APP_SECRET
    )
    try:
        user = api.get_me(user_fields=['public_metrics', 'verified', 'description'])
        details = {
            'screen_name': user.data.username,
            'name': user.data.name,
            'description': getattr(user.data, 'description', None),
            'verified': getattr(user.data, 'verified', None),
            'followers_count': user.data.public_metrics.get('followers_count', 0),
            'friends_count': user.data.public_metrics.get('following_count', 0),
            'statuses_count': user.data.public_metrics.get('tweet_count', 0),
            'id': user.data.id
        }
    except Exception as e:
        log.setLevel(old_level)
        raise e
    log.setLevel(old_level)
    return details


def get_follower_count(log, id):
    log.debug("Getting follower count for %s", id)
    details = get_account_details(log, id)
    if details:
        log.debug("%d", details["followers_count"])
        return details["followers_count"]
    else:
        return None


def get_screen_name(log):
    global MYSELF
    if not MYSELF or MYSELF == "Unknown":
        log.debug("Getting current user screen name")
        check_twitter_config()
        logging.captureWarnings(True)
        old_level = log.getEffectiveLevel()
        log.setLevel(logging.ERROR)
        twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
        try:
            details = twitter.verify_credentials()
        except TwythonAuthError as e:
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
    log.debug("Getting people %s is following", id)
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
        except TwythonAuthError as e:
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
            log.debug("Sleeping %ds to avoid rate limit. Cursor: %s", s, cursor)
            time.sleep(s)
        else:
            log.debug("Normal query end")

        max_loops -= 1
        if max_loops <= 0:
            log.debug("Killing search due to max loops")
            break
    log.setLevel(old_level)


def get_followers(log, id):
    log.debug("Getting people following %s", id)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    api = tweepy.Client(
        bearer_token=BEARER_TOKEN,
        access_token=OAUTH_TOKEN,
        access_token_secret=OAUTH_TOKEN_SECRET,
        consumer_key=APP_KEY,
        consumer_secret=APP_SECRET
    )
    log.setLevel(old_level)

    try:
        user = api.get_user(username=id)
        user_id = user.data.id
    except Exception as e:
        log.setLevel(old_level)
        log.exception("Problem getting user %s", id)
        raise

    pagination_token = None
    max_loops = 15
    while True:
        try:
            log.setLevel(logging.ERROR)
            response = api.get_users_followers(id=user_id, max_results=1000, pagination_token=pagination_token)
            log.setLevel(old_level)
        except Exception as e:
            log.setLevel(old_level)
            log.exception("Problem getting followers for %s", id)
            raise
        if response.data:
            for u in response.data:
                yield {'screen_name': u.username}
        if response.meta and 'next_token' in response.meta:
            pagination_token = response.meta['next_token']
        else:
            log.debug("Pagination end")
            break

        max_loops -= 1
        if max_loops <= 0:
            log.debug("Killing search due to max loops")
            break

    log.setLevel(old_level)


def favorite_tweet(log, id):
    log.debug("Favoriting tweet % s", id)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    log.setLevel(old_level)
    try:
        log.setLevel(logging.ERROR)
        res = twitter.create_favorite(id=id)
        log.setLevel(old_level)
        return res
    except TwythonAuthError as e:
        log.setLevel(old_level)
        if 'You have already favorited this status' in str(e):
            log.info("tweet already favorited")
        else:
            log.exception("Problem trying to favorite tweet")
            twitter_auth_issue(e)
        raise


def retweet_tweet(log, id):
    log.debug("Retweeting tweet % s", id)
    check_twitter_config()
    logging.captureWarnings(True)
    old_level = log.getEffectiveLevel()
    log.setLevel(logging.ERROR)
    twitter = Twython(APP_KEY, APP_SECRET, OAUTH_TOKEN, OAUTH_TOKEN_SECRET)
    log.setLevel(old_level)
    try:
        log.setLevel(logging.ERROR)
        res = twitter.retweet(id=id)
        log.setLevel(old_level)
        return res
    except TwythonAuthError as e:
        log.setLevel(old_level)
        if 'You have already retweeted this status' in str(e):
            log.info("tweet already retweeted")
        else:
            log.exception("Problem trying to retweeted tweet")
            twitter_auth_issue(e)
        raise


def main():
    parser = argparse.ArgumentParser(description='Tweet testing')
    parser.add_argument('--pic', help='Tweet a picture', required=False, action='store_true')
    parser.add_argument('--followers', help='Get list of followers for a username', required=False)
    parser.add_argument('--user', help='Get user details for a username', required=False)
    parser.add_argument('--me', help='Get details for the authenticated user', required=False, action='store_true')
    parser.add_argument('--following', help='Get list of users followed by a username', required=False)
    parser.add_argument('--follow', help='Follow a user', required=False)
    parser.add_argument('--unfollow', help='Unfollow a user', required=False)
    parser.add_argument('--like', help='Like a tweet by ID', required=False)
    parser.add_argument('--retweet', help='Retweet a tweet by ID', required=False)
    parser.add_argument('--relationship', help='Check relationship with a user', required=False)
    parser.add_argument('--screenname', help='Get my screen name', required=False, action='store_true')
    parser.add_argument('--follower-count', help='Get follower count for a username', required=False)
    parser.add_argument('--search', help='Search tweets', required=False)
    args = parser.parse_args()

    log = logging.getLogger(__name__)

    if args.followers:
        try:
            for user in get_followers(log, args.followers):
                print(user['screen_name'])
        except Exception as e:
            print(f"Error getting followers: {e}", file=sys.stderr)
    elif args.user:
        try:
            details = get_account_details(log, args.user)
            if details:
                print(f"Username: {details.get('screen_name', 'N/A')}")
                print(f"Name: {details.get('name', 'N/A')}")
                print(f"Description: {details.get('description', 'N/A')}")
                print(f"Verified: {details.get('verified', 'Unknown')}")
                print(f"Followers: {details.get('followers_count', 'N/A')}")
                print(f"Following: {details.get('friends_count', 'N/A')}")
                print(f"Tweets: {details.get('statuses_count', 'N/A')}")
            else:
                print("User not found", file=sys.stderr)
        except Exception as e:
            print(f"Error getting user: {e}", file=sys.stderr)
    elif args.me:
        try:
            details = get_self_details(log)
            print(f"Username: {details.get('screen_name', 'N/A')}")
            print(f"Name: {details.get('name', 'N/A')}")
            print(f"Description: {details.get('description', 'N/A')}")
            print(f"Verified: {details.get('verified', 'Unknown')}")
            print(f"Followers: {details.get('followers_count', 'N/A')}")
            print(f"Following: {details.get('friends_count', 'N/A')}")
            print(f"Tweets: {details.get('statuses_count', 'N/A')}")
        except Exception as e:
            print(f"Error getting authenticated user: {e}", file=sys.stderr)
    elif args.following:
        try:
            for screen_name in get_following(log, args.following):
                print(screen_name)
        except Exception as e:
            print(f"Error getting following: {e}", file=sys.stderr)
    elif args.follow:
        try:
            follow_twitter_user(log, args.follow)
            print("Followed")
        except Exception as e:
            print(f"Error following user: {e}", file=sys.stderr)
    elif args.unfollow:
        try:
            unfollow_twitter_user(log, args.unfollow)
            print("Unfollowed")
        except Exception as e:
            print(f"Error unfollowing user: {e}", file=sys.stderr)
    elif args.like:
        try:
            favorite_tweet(log, args.like)
            print("Liked")
        except Exception as e:
            print(f"Error liking tweet: {e}", file=sys.stderr)
    elif args.retweet:
        try:
            retweet_tweet(log, args.retweet)
            print("Retweeted")
        except Exception as e:
            print(f"Error retweeting tweet: {e}", file=sys.stderr)
    elif args.relationship:
        try:
            following, followed_by = check_relationship(log, args.relationship)
            print(f"You are following {args.relationship}: {following}")
            print(f"{args.relationship} is following you: {followed_by}")
        except Exception as e:
            print(f"Error checking relationship: {e}", file=sys.stderr)
    elif args.screenname:
        try:
            screen_name = get_screen_name(log)
            print(f"Your screen name: {screen_name}")
        except Exception as e:
            print(f"Error getting screen name: {e}", file=sys.stderr)
    elif args.follower_count:
        try:
            count = get_follower_count(log, args.follower_count)
            if count is not None:
                print(f"Followers: {count}")
            else:
                print("User not found", file=sys.stderr)
        except Exception as e:
            print(f"Error getting follower count: {e}", file=sys.stderr)
    elif args.search:
        try:
            result = tweet_search(log, args.search, limit=10)
            if 'statuses' in result and result['statuses']:
                for i, status in enumerate(result['statuses'][:5]):
                    print(f"{i+1}. {status.get('text', '')[:140]}...")
            else:
                print("No results")
        except Exception as e:
            print(f"Error searching tweets: {e}", file=sys.stderr)
    elif args.pic:
        pic = random.choice(glob.glob('images/*.jpg'))
        message = "One of my favorite pictures"
        print(f"Tweeting: '{message}' with pic: {pic}")
        tweet_string(message=message, log=log, media=pic)
    else:
        parser.print_help()


if __name__ == '__main__':
        main()
