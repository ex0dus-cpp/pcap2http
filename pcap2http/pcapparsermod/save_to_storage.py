from __future__ import unicode_literals, print_function, division

class SaveToStorage(object):
    def __init__(self, client_host, remote_host, storage):
        self.host = ''
        self.uri = ''
        self.storage = storage

    def on_http_req(self, req_header, req_body, numbers):
        """
        :type req_header: HttpRequestHeader
        :type req_body: bytes
        """
        self.host = req_header.host.decode()
        self.uri = req_header.uri.decode()
        
        self.storage.setdefault(self.host, dict())
        if self.uri in self.storage[self.host]:
            head, body, old_numbers = self.storage[self.host][self.uri]
            if body is None: body = b''
            self.storage[self.host][self.uri] = head, body, (old_numbers | numbers)
        else:
            self.storage[self.host].setdefault(self.uri, ('', b'', set(numbers)))
        #print(self.storage[self.host][self.uri])

    def on_http_resp(self, resp_header, resp_body, numbers):
        """
        :type resp_header: HttpResponseHeader
        :type resp_body: bytes
        """
        head, body, old_numbers = self.storage[self.host][self.uri]
        if resp_body is None: resp_body = b''
        self.storage[self.host][self.uri] = resp_header.raw_data.decode(), resp_body, (old_numbers | numbers)
        #print(self.host + self.uri, old_numbers | numbers)

    def finish(self):
        """called when this connection finished"""
        pass