CACHE = True  # TODO It doesn't work for now :(

MASTER = "http://10.34.24.173/faf/"

VERBOSE = True

step_1 = ['ERRATA']  # Bugzilla bugs with closed Fedora Bugzilla bugs

if True:

    SLAVE = {'request_server_min': "http://10.34.24.108:8080/faf/",
             'request_server_min_2': "http://10.34.24.108:8080/faf/"
             }

else:
    SLAVE = {'request_server_min': "http://10.34.24.108:8080/faf/"}
    # SLAVE = {'request_server_min': "http://10.34.24.173/faf/"}

