MASTER = "http://patrikhelia.cz/master.php"
DEBUG = False
CACHE = True

if True:

    SLAVE = {'server1': "http://patrikhelia.cz/request.php",
             'server2': "http://patrikhelia.cz/request.php",
             'request_server': "http://patrikhelia.cz/request.php"}

else:
    SLAVE = {'request_server': "http://patrikhelia.cz/request.php"}
