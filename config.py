from datetime import datetime
CACHE = True

MASTER = "http://example.com/faf/"

BZ_USER = ""
BZ_PASSWORD = ""

SLAVE = {'request_server': "http://example.com/faf/"}

# Example for multiple servers
# SLAVE = {'request_server_min': "http://example.com/faf/",
#           'request_server_min_2': "http://example1.com/faf/"}

WATSON_URL = "http://watson-pgm.itos.redhat.com/ng/getsubsysbyassignee"

# Smtp server address
EMAIL_SMTP = "localhost"
# Email address from which will be email sended
EMAIL_FROM = "example@redhat.com"
# Email address of recipients
EMAIL_TO = ['example@example.com']
#Email subject
EMAIL_SUBJECT = "ABRT RHEL-7 crash statistics report {}".format(datetime.now().strftime("%Y-%m"))
