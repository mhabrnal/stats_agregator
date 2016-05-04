CACHE = True  # TODO It doesn't work for now :(

MASTER = "http://10.34.24.173/faf/"

if True:

    SLAVE = {'server1': "http://10.34.24.173/faf/",
             'server2': "http://10.34.24.173/faf/"
             }

else:
    SLAVE = {'request_server': "http://10.34.24.173/faf/"}

