import pickle
import os


def save_binary_cache(file_name, variable):
    if not os.path.isfile("cache/" + file_name):
        with open("cache/" + file_name, "wb") as f:
            f.write(pickle.dumps(variable))


def load_binary_cache(file_name):
    if os.path.isfile("cache/" + file_name):
        r_val = dict()
        with open("cache/" + file_name, "rb") as f:
            try:
                r_val = pickle.load(f)
                print "Load {0}".format(file_name)
            except pickle.UnpicklingError as e:
                print "{0}".format(e.message)
                exit()
        return r_val
    return None


def delete_cache_file(file_name):
    if os.path.isfile("cache/" + file_name):
        pass  # try to delete
    print "Iam deleting {0} file.".format(file_name)
