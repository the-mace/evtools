#!/usr/bin/env python
# encoding: utf-8
"""
tl_stock.py

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

Stock quote helper functions
"""

import urllib.request, urllib.parse, urllib.error
import json
import os


def get_stock_quote(stock, log):
    """
    https://polygon.io/docs/stocks/get_v2_aggs_ticker__stocksticker__prev
    :param stock:
    :param log:
    :return:
    """
    log.debug("Get current stock quote for %s" % stock)
    token = os.getenv("TL_POLYGON_TOKEN")

    data = urllib.request.urlopen(
        f"https://api.polygon.io/v2/aggs/ticker/{stock}/prev?adjusted=true&apiKey={token}"
    ).read()
    json_response = json.loads(data)
    if json_response:
        quote = json_response["results"][0]['c']
    else:
        quote = None
    return quote
