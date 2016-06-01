# Abstract Class for served master and slave server
from abc import ABCMeta, abstractmethod
import json
import urllib2
import os


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

    def save_cache(self, file_name, data):
        print "Save cache to file '{0}'".format(file_name)

        with open("cache/" + file_name, "w") as f:
            f.write(json.dumps(data))

    def fast_load(self, file_name):
        '''
        Working method for fast load json cache
        '''
        file_path = ""
        if os.path.isfile(str(file_name)):
            file_path = file_name
        elif os.path.isfile("cache/" + str(file_name)):
            file_path = "cache/" + str(file_name)
        else:
            raise "File doesn't exist"
            return False

        data = ""
        with open(file_path, "r") as f:
            for line in f:
                data += line
        return json.loads(data)

    @staticmethod
    def download_data(url, data):
        problem_url = url + "reports/items/"

        json_data_send = json.dumps(data)

        request = urllib2.Request(problem_url, data=json_data_send,
                                  headers={"Content-Type": "application/json",
                                           "Accept": "application/json"})

        data = urllib2.urlopen(request)

        json_string = data.read()
        return json_string
