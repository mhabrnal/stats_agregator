# Abstract Class for served master and slave server
import json
import os
from abc import ABCMeta, abstractmethod
from datetime import datetime


class AServer:
    __metaclass__ = ABCMeta

    master_bt = []
    slave_bt = dict()
    master_problem = []
    slave_problem = dict()

    @abstractmethod
    def __init__(self):
        pass

    def load_cache(self, file_name):
        if os.path.isfile("cache/" + file_name):
            print "Trying load data from {0}".format(file_name)
            parsed_json = ""
            with open("cache/" + file_name, "r") as f:
                for line in f:
                    parsed_json = self.parse_hash_from_json(line)
            return parsed_json
        return False

    @staticmethod
    def parse_hash_from_json(json_string):
        print "We are going to parse json"
        try:
            js = json.loads(json_string)
        except ValueError:
            str_name = "log/json_error_{0}.log".format(datetime.now())
            with open(str_name, "w") as f:
                f.write(json_string)
                print "JSON Can't be parsed. String was saved to {0}".format(str_name)
                exit()
        return js

    '''
    #m
    def load_cache(self):
        if os.path.isfile("cache/" + self.master_file):
            with open("cache/" + self.master_file, "r") as f:
                for line in f:
                    self.parse_hash_from_json(line)
            return True
        else:
            return False
    #S
    def load_cache(self):
        for server_name, server_url in self.url.items():
            if os.path.isfile("cache/" + server_name + ".json"):
                with open("cache/" + server_name + ".json", "r") as f:
                    for line in f:
                        self.slave_bt[server_name] = self.parse_hash_from_json(line)
                return True
            else:
                return False
    '''
    '''
    # TODO Use from AServer?
    #M
    def parse_hash_from_json(self, json_string):
        self.master_bt = (json.loads(json_string))
        if 'data' in self.master_bt:
            self.master_bt = self.master_bt['data']
        else:
            self.master_bt = self.master_bt

    #S
    def parse_hash_from_json(json_string):
        try:
            js = json.loads(json_string)
        except ValueError:
            str_name = "log/json_error_{0}.log".format(datetime.now())
            with open(str_name, "w") as f:
                f.write(json_string)
                print "JSON Can't be parsed. String was saved to {0}".format(str_name)
                exit()
        return js

    '''
