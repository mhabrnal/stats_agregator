# Abstract Class for served master and slave server
from abc import ABCMeta, abstractmethod


class AServer:
    __metaclass__ = ABCMeta

    @abstractmethod
    def __init__(self):
        pass

    @abstractmethod
    def load(self):
        pass

    @abstractmethod
    def save_cache(self):
        pass

    @abstractmethod
    def load_cache(self):
        pass
