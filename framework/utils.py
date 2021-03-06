import os
import pickle
import re
import json
import urllib
import urllib2
import config
import sys

from pprint import pprint
from datetime import datetime
from pkg_resources import parse_version
from time import sleep


def save_binary_cache(file_name, variable, force_write=True):
    if not os.path.isfile("cache/" + file_name) or force_write:
        with open("cache/" + file_name, "wb") as f:
            f.write(pickle.dumps(variable))


def load_binary_cache(file_name):
    r_val = dict()
    if os.path.isfile("cache/" + file_name):
        with open("cache/" + file_name, "rb") as f:
            try:
                r_val = pickle.load(f)
                print "Load {0}".format(file_name)
            except pickle.UnpicklingError as e:
                print "{0}".format(e.message)
                exit()
    return r_val


def clear_cache():
    """
    Delete all cached file
    """
    files = os.listdir("cache")
    for f in files:
        os.unlink("cache/" + f)
        print "Delete cache cache/" + f


def get_lastes_version(package_counts, component):
    last_version = ""
    for item in package_counts:
        if re.search("^" + component, item[0]):
            item[-1].sort(key=lambda x: parse_version(x[0]), reverse=True)
            last_version = item[-1][0][0]

    return re.sub('^([0-9]:)?', '', last_version)


def get_first_version(package_counts, component):
    first_version = ""
    for item in package_counts:
        if re.search("^" + component, item[0]):
            item[-1].sort(key=lambda x: parse_version(x[0]))
            first_version = item[-1][0][0]

    return re.sub('^([0-9]:)?', '', first_version)


def get_opsys(releases):
    os = []
    for r in releases:
        os.append(re.search('^[a-zA-Z ]*', r['name']).group(0).strip(" "))
    return os


def json_to_date(json_date):
    try:
        d = datetime.strptime(json_date, '%Y-%m-%dT%H:%M:%S.%f')
    except:
        try:
            d = datetime.strptime(json_date, '%Y-%m-%dT%H:%M:%S')
        except ValueError:
            print "Time data does not match allowed format."

    return d


def date_diff(first, last):
    diff = last - first

    year = diff.days / 365
    months = round((diff.days / 30.4) - (year * 12))

    spell_m = "month"
    if months > 1:
        spell_m = "months"

    spell_y = "year"
    if year > 1:
        spell_y = "years"

    if year > 0 and months > 0:
        return "~ {0} {1} {2} {3}".format(year, spell_y, str(int(months)), spell_m)
    elif year > 0:
        return "~ {0} {1}".format(year, spell_y)
    elif months > 0:
        return "~ {0} {1}".format(str(int(months)), spell_m)
    else:
        return "~1 month"


def bugzilla_url(bz_bug):
    if bz_bug is not False:
        status = bz_bug.status
        if bz_bug.resolution in ['EOL', 'WONTFIX']:
            return ""

        if bz_bug.status == "CLOSED":
            status += " {0}".format(bz_bug.resolution)

        return "\t- https://bugzilla.redhat.com/{0} - {1}\n".format(bz_bug.id, status)


def strip_name_from_version(version):
    return str(re.sub('^([a-zA-Z0-9\-]*-)?([0-9]:)?', '', version))


def get_mount_count(first, last):
    diff = last - first
    r_d = diff.days / 30.4
    if r_d < 1:
        return 1
    return round(r_d)


def watson_api(component_name, assignee):
    data = urllib.urlencode({
        "assignee": assignee,
        "component": component_name,
    })

    for i in range(0, 10):
        try:
            return json.load(urllib2.urlopen(config.WATSON_URL, data))
        except urllib2.HTTPError, e:
            sleep(2)
            print "Retrying {0} - {1}".format(config.WATSON_URL, e)


def save_cache(file_name, data):
    print "Save cache to file '{0}'".format(file_name)
    if not os.path.isdir('cache'):
        os.mkdir('cache')

    with open("cache/" + file_name, "w") as f:
        f.write(json.dumps(data))


def download_data(url, data):  # TODO rename this method
    problem_url = url + "reports/items/"

    json_data_send = json.dumps(data)

    request = urllib2.Request(problem_url, data=json_data_send,
                              headers={"Content-Type": "application/json",
                                       "Accept": "application/json"})

    try:
        print "Open connection for download ureports ({})".format(url)
        data = urllib2.urlopen(request)
    except urllib2.HTTPError as e:
        print "While trying download '" + problem_url + "' we get error code: " + str(e.code)
        print e
        sys.exit()
    else:
        json_string = data.read()

    return json_string
