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

Description:

Email helper functions
"""

import smtplib
import os
from email.mime.text import MIMEText

# Initialize Mail Items
DEFAULT_TL_SMTP_SERVER = "127.0.0.1"
DEFAULT_TL_MAILFROM = "nobody@example.com"


if 'TL_SMTP_SERVER' in os.environ:
    TL_SMTP_SERVER = os.environ['TL_SMTP_SERVER']
else:
    TL_SMTP_SERVER = DEFAULT_TL_SMTP_SERVER


if 'TL_MAILFROM' in os.environ:
    TL_MAILFROM = os.environ['TL_MAILFROM']
else:
    TL_MAILFROM = DEFAULT_TL_MAILFROM


def email(email, message, subject):
    """
    Send an email to someone
    :param email: Target for email
    :param message: The message to send
    :param subject: The subject of the message
    :return: None
    """
    msg = MIMEText(message.encode('utf-8').strip())

    # make sure the user provided all the parameters
    if not email:
        return "A required parameter is missing, \
               please go back and correct the error"

    # create the message text
    msg['Subject'] = subject
    msg['From'] = TL_MAILFROM
    msg['To'] = email

    server = smtplib.SMTP(TL_SMTP_SERVER)
    server.sendmail(TL_MAILFROM, [email], msg.as_string())
    server.quit()
