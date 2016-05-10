CACHE = True  # TODO It doesn't work for now :(

MASTER = "http://10.34.24.173/faf/"

if False:

    SLAVE = {'server1': "http://10.34.24.108/faf/",
             'server2': "http://10.34.24.108/faf/"
             }

else:
    SLAVE = {'request_server_min': "http://10.34.24.108:8080/faf/"}

