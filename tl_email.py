#!/usr/bin/env python
# encoding: utf-8
"""
tl_email.py

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

Email helper functions
"""

import smtplib
import os
from email.mime.text import MIMEText

# Initialize Mail Items
DEFAULT_TL_SMTP_SERVER = "127.0.0.1"
DEFAULT_TL_SMTP_PORT = 25
DEFAULT_TL_MAILFROM = "nobody@example.com"
DEFAULT_TL_SMTP_USER = None
DEFAULT_TL_SMTP_PASSWORD = None

if 'TL_SMTP_SERVER' in os.environ:
    TL_SMTP_SERVER = os.environ['TL_SMTP_SERVER']
else:
    TL_SMTP_SERVER = DEFAULT_TL_SMTP_SERVER

if 'TL_SMTP_PORT' in os.environ:
    TL_SMTP_PORT = os.environ['TL_SMTP_PORT']
else:
    TL_SMTP_PORT = DEFAULT_TL_SMTP_PORT

if 'TL_SMTP_USER' in os.environ:
    TL_SMTP_USER = os.environ['TL_SMTP_USER']
else:
    TL_SMTP_USER = DEFAULT_TL_SMTP_USER

if 'TL_SMTP_PASSWORD' in os.environ:
    TL_SMTP_PASSWORD = os.environ['TL_SMTP_PASSWORD']
else:
    TL_SMTP_PASSWORD = DEFAULT_TL_SMTP_PASSWORD

if 'TL_MAILFROM' in os.environ:
    TL_MAILFROM = os.environ['TL_MAILFROM']
else:
    TL_MAILFROM = DEFAULT_TL_MAILFROM


def email(email, message, subject, cc=None, bcc=None):
    msg = MIMEText(message.encode('utf-8').strip())

    # make sure the user provided all the parameters
    if not email:
        raise Exception("A required parameter is missing, please go back and correct the error")

    # create the message text
    msg['Subject'] = subject
    msg['From'] = TL_MAILFROM
    msg['To'] = email

    to_addr = [email]
    if cc:
        msg['CC'] = ",".join(cc)
        to_addr += cc
    if bcc:
        to_addr += bcc

    # Here we're assuming if its local host sending email there's no login/security, otherwise its secure
    if TL_SMTP_SERVER != DEFAULT_TL_SMTP_SERVER or TL_SMTP_PORT != 25:
        server = smtplib.SMTP(TL_SMTP_SERVER, TL_SMTP_PORT)
        server.ehlo()
        server.starttls()
        server.login(TL_SMTP_USER, TL_SMTP_PASSWORD)
        server.sendmail(TL_MAILFROM, to_addr, msg.as_string())
        server.quit()
    else:
        server = smtplib.SMTP(TL_SMTP_SERVER)
        server.sendmail(TL_MAILFROM, to_addr, msg.as_string())
        server.quit()
