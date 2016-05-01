from __future__ import unicode_literals, print_function, division

from io import StringIO
import sys

from pcapparser.config import OutputLevel
# print http req/resp
from pcapparser import utils, six
from pcapparser import config
import threading
from pcapparser.constant import Compress

printer_lock = threading.Lock()

def _get_full_url(uri, host):
    if uri.startswith(b'http://') or uri.startswith(b'https://'):
        return uri
    else:
        return b'http://' + host + uri


class SaveToStorage(object):
    def __init__(self, client_host, remote_host, storage):
        #self.parse_config = config.get_config()
        #self.buf = StringIO()
        #self.client_host = client_host
        #self.remote_host = remote_host
        self.host = ''
        self.uri = ''
        self.storage = storage

    def on_http_req(self, req_header, req_body):
        """
        :type req_header: HttpRequestHeader
        :type req_body: bytes
        """
        self.host = req_header.host.decode()
        self.uri = req_header.uri.decode()
        
        self.storage.setdefault(self.host, dict())
        self.storage[self.host].setdefault(self.uri, ('', b''))

    def on_http_resp(self, resp_header, resp_body):
        """
        :type resp_header: HttpResponseHeader
        :type resp_body: bytes
        """
        self.storage[self.host][self.uri] = resp_header.raw_data.decode(), resp_body #

    def finish(self):
        """called when this connection finished"""
        pass