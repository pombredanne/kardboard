import datetime
import re

import translitcodec
from dateutil.relativedelta import relativedelta

from kardboard import app


def business_days_between(date1, date2):
    if date1 < date2:
        oldest_date, youngest_date = date1, date2
    else:
        oldest_date, youngest_date = date2, date1

    business_days = 0
    date = oldest_date
    while date < youngest_date:
        if date.weekday() != 5 and date.weekday() != 6:
            business_days += 1
        date = date + datetime.timedelta(days=1)
    return business_days


def month_range(date):
    start = date.replace(day=1, hour=0, minute=0, second=0)
    end = start + relativedelta(months=+1) + relativedelta(days=-1)
    return start, end


def week_range(date):
    day_type = date.isoweekday()
    end_diff = 6 - day_type
    end_date = date + relativedelta(days=end_diff)
    start_date = end_date - relativedelta(days=6)

    start_date = make_start_date(date=start_date)
    end_date = make_end_date(date=end_date)

    return start_date, end_date


def make_start_date(year=None, month=None, day=None, date=None):
    start_date = munge_date(year, month, day, date)
    start_date = start_date.replace(hour=23, minute=59, second=59)
    start_date = start_date.replace(hour=0, minute=0, second=0)
    return start_date


def make_end_date(year=None, month=None, day=None, date=None):
    end_date = munge_date(year, month, day, date)
    end_date = end_date.replace(hour=23, minute=59, second=59)
    return end_date


def munge_date(year=None, month=None, day=None, date=None):
    """
    Takes a given datetime, or now(), and sets its
    year, month and day to any of those values passed in
    optionally.
    """
    if not date:
        date = datetime.datetime.now()

    year = year or date.year
    month = month or date.month
    day = day or date.day

    date = date.replace(year=year, month=month, day=day, microsecond=0)
    return date

_punct_re = re.compile(r'[\t !"#$%&\'()*\-/<=>?@\[\\\]^_`{|},.]+')


def slugify(text, delim=u'-'):
    """Generates an ASCII-only slug."""
    result = []
    for word in _punct_re.split(text.lower()):
        word = word.encode('translit/long')
        if word:
            result.append(word)
    return unicode(delim.join(result))


@app.template_filter()
def timesince(dt, default="just now"):
    """
    Returns string representing "time since" e.g.
    3 days ago, 5 hours ago etc.
    """

    now = datetime.datetime.now()
    diff = now - dt

    periods = (
        (diff.days / 365, "year", "years"),
        (diff.days / 30, "month", "months"),
        (diff.days / 7, "week", "weeks"),
        (diff.days, "day", "days"),
        (diff.seconds / 3600, "hour", "hours"),
        (diff.seconds / 60, "minute", "minutes"),
        (diff.seconds, "second", "seconds"),
    )

    for period, singular, plural in periods:

        if period:
            return "%d %s ago" % (period, singular if period == 1 else plural)

    return default