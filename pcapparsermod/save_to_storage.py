from __future__ import unicode_literals, print_function, division

class SaveToStorage(object):
    def __init__(self, client_host, remote_host, storage):
        self.host = ''
        self.uri = ''
        self.storage = storage
        self.numbers = set()

    def on_http_req(self, req_header, req_body, numbers):
        """
        :type req_header: HttpRequestHeader
        :type req_body: bytes
        """
        self.host = req_header.host.decode()
        self.uri = req_header.uri.decode()
        
        self.storage.setdefault(self.host, dict())
        self.storage[self.host].setdefault(self.uri, ('', b''))
        self.numbers |= numbers

    def on_http_resp(self, resp_header, resp_body, numbers):
        """
        :type resp_header: HttpResponseHeader
        :type resp_body: bytes
        """
        self.storage[self.host][self.uri] = resp_header.raw_data.decode(), resp_body
        self.numbers |= numbers
        #print(self.host + self.uri, self.numbers)

    def finish(self):
        """called when this connection finished"""
        pass