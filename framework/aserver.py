# Abstract Class for served master and slave server
import json
import sys
import urllib2
from abc import ABCMeta, abstractmethod


class AServer:
    __metaclass__ = ABCMeta

    master_bt = []
    slave_bt = dict()
    master_problem = []
    slave_problem = dict()

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def load_cache(self):  # TODO RE IMPLEMENT FROM CHILD CLASSES
        pass

    #TODO probably move to utils
    def save_cache(self, file_name, data):
        print "Save cache to file '{0}'".format(file_name)

        with open("cache/" + file_name, "w") as f:
            f.write(json.dumps(data))

    # TODO probably move to utils
    @staticmethod
    def download_data(url, data):
        problem_url = url + "reports/items/"

        json_data_send = json.dumps(data)

        request = urllib2.Request(problem_url, data=json_data_send,
                                  headers={"Content-Type": "application/json",
                                           "Accept": "application/json"})
        try:
            data = urllib2.urlopen(request)
        except urllib2.HTTPError as e:
            print "While tring download '" + problem_url + "' we get error code: " + str(e.code)
            sys.exit()
        else:
            json_string = data.read()

        return json_string
