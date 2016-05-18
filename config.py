CACHE = True

MASTER = "http://10.34.24.173/faf/"

VERBOSE = True

BUG_TYPE = ['ERRATA']  # Bugzilla bugs with closed Fedora Bugzilla bugs

if False:
    SLAVE = {'request_server_min': "http://10.34.24.108:8080/faf/",
             'request_server_min_2': "http://10.34.24.108:8080/faf/"
             }

else:
    SLAVE = {'request_server': "http://10.34.24.108:8080/faf/"}
    # SLAVE = {'request_server_min': "http://10.34.24.173/faf/"}
