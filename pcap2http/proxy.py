import sys
import os
import socket
import ssl
import select
import http.client
import urllib.parse
import threading
import gzip
import zlib
import time
import json
import re
from http.server import HTTPServer, BaseHTTPRequestHandler
from socketserver import ThreadingMixIn
from io import BytesIO
from subprocess import Popen, PIPE
from html.parser import HTMLParser
from collections import OrderedDict

#from urllib.parse import *

storage = dict()
debug = False


def filter_headers(headers):
    # http://tools.ietf.org/html/rfc2616#section-13.5.1
    hop_by_hop = ['connection', 'keep-alive', 'proxy-authenticate', 'proxy-authorization', 'te', 'trailers',
                  'transfer-encoding', 'upgrade']
    # hop_by_hop.extend(['content-encoding'])
    for k in hop_by_hop:
        if k in headers:
            del headers[k]
    return headers


def encode_content_body(text, encoding):
    if encoding == 'identity':
        data = text
    elif encoding in ('gzip', 'x-gzip'):
        io = BytesIO()
        with gzip.GzipFile(fileobj=io, mode='wb') as f:
            f.write(text)
        data = io.getvalue()
    elif encoding == 'deflate':
        data = zlib.compress(text)
    else:
        raise Exception("Unknown Content-Encoding: %s" % encoding)
    return data


def decode_content_body(data, encoding):
    if encoding == 'identity':
        text = data
    elif encoding in ('gzip', 'x-gzip'):
        io = BytesIO(data)
        with gzip.GzipFile(fileobj=io) as f:
            text = f.read()
    elif encoding == 'deflate':
        try:
            text = zlib.decompress(data)
        except zlib.error:
            text = zlib.decompress(data, -zlib.MAX_WBITS)
    else:
        raise Exception("Unknown Content-Encoding: %s" % encoding)
    return text


def get_plain_resp(res):
    res_body = res.read()
    version_table = {10: 'HTTP/1.0', 11: 'HTTP/1.1'}
    setattr(res, 'headers', res.msg)
    setattr(res, 'response_version', version_table[res.version])

    content_encoding = res.headers.get('Content-Encoding', 'identity')
    return res_body, decode_content_body(res_body, content_encoding), content_encoding

def headers_dict_to_str(headers):
    head = ''
    for name, value in headers.items():
        head += name + ':' + value + '\r\n'
    return head

def get_response_from_storage(storage_item, key=''):
    head, body, numbers = storage_item

    headers = OrderedDict()
    for line in head.split('\n'):
        spl = tuple(line.split(':', 1))
        if len(spl) != 2:
            headers.setdefault(spl[0], '')
        else:
            name, value = spl
            headers.setdefault(name.lower(), value)
    headers = filter_headers(headers)

    head = headers_dict_to_str(headers)
    full = head.encode() + b'\r\n' + body

    '''
    if debug:
        try:
            os.mkdir('responses')
        except Exception:
            pass
        with open('responses/%s.txt' % key, 'wb') as f:
            f.write(full)
            f.flush()
    '''

    source = FakeSocket(full)
    response = http.client.HTTPResponse(source)
    response.begin()
    return response


def check_storage(host, path):
    spl = list(urllib.parse.urlsplit(path))
    spl[0] = spl[1] = ''
    uri = urllib.parse.urlunsplit(spl)

    '''
    if self.debug:
        with self.lock:
            print('==============')
            print(self.path, self.headers['host'], uri)
            print(self.headers['host'] in self.storage, self.storage.keys())
            if self.headers['host'] in self.storage:
                print(uri in self.storage[self.headers['host']], self.storage[self.headers['host']].keys())
    '''
    if host in storage and uri in storage[host]:
        return get_response_from_storage(storage[host][uri])
    return None

def with_color(c, s):
    return "\x1b[%dm%s\x1b[0m" % (c, s)


class ThreadingHTTPServer(ThreadingMixIn, HTTPServer):
    address_family = socket.AF_INET
    daemon_threads = True

    def handle_error(self, request, client_address):
        # surpress socket/ssl related errors
        cls, e = sys.exc_info()[:2]
        if cls is socket.error or cls is ssl.SSLError:
            pass
        else:
            return HTTPServer.handle_error(self, request, client_address)

class FakeSocket():
    def __init__(self, response_str):
        self._file = BytesIO(response_str)
    def makefile(self, *args, **kwargs):
        return self._file

class ProxyRequestHandler(BaseHTTPRequestHandler):
    cakey = 'ca.key'
    cacert = 'ca.crt'
    certkey = 'cert.key'
    certdir = 'certs/'
    timeout = 5
    lock = threading.Lock()
    allow_requests = True
    stderr_print = False

    def __init__(self, *args, **kwargs):
        self.tls = threading.local()
        self.tls.conns = {}

        BaseHTTPRequestHandler.__init__(self, *args, **kwargs)

    def log_message(self, format, *args):
        if self.stderr_print:
            sys.stderr.write("%s - - [%s] %s\n" %
                             (self.address_string(),
                              self.log_date_time_string(),
                              format%args))
    
    def log_error(self, format, *args):
        # surpress "Request timed out: timeout('timed out',)"
        if isinstance(args[0], socket.timeout):
            return

        self.log_message(format, *args)

    def do_CONNECT(self):
        if os.path.isfile(self.cakey) and os.path.isfile(self.cacert) and os.path.isfile(self.certkey) and os.path.isdir(self.certdir):
            self.connect_intercept()
        else:
            self.connect_relay()

    def connect_intercept(self):
        hostname = self.path.split(':')[0]
        certpath = "%s/%s.crt" % (self.certdir.rstrip('/'), hostname)

        with self.lock:
            if not os.path.isfile(certpath):
                epoch = "%d" % (time.time() * 1000)
                p1 = Popen(["openssl", "req", "-new", "-key", self.certkey, "-subj", "/CN=%s" % hostname], stdout=PIPE)
                p2 = Popen(["openssl", "x509", "-req", "-days", "3650", "-CA", self.cacert, "-CAkey", self.cakey, "-set_serial", epoch, "-out", certpath], stdin=p1.stdout, stderr=PIPE)
                p2.communicate()

        self.wfile.write("%s %d %s\r\n" % (self.protocol_version, 200, 'Connection Established'))
        self.end_headers()

        self.connection = ssl.wrap_socket(self.connection, keyfile=self.certkey, certfile=certpath, server_side=True)
        self.rfile = self.connection.makefile("rb", self.rbufsize)
        self.wfile = self.connection.makefile("wb", self.wbufsize)

        conntype = self.headers.get('Proxy-Connection', '')
        if conntype.lower() == 'close':
            self.close_connection = 1
        elif (conntype.lower() == 'keep-alive' and self.protocol_version >= "HTTP/1.1"):
            self.close_connection = 0

    def connect_relay(self):
        address = self.path.split(':', 1)
        address[1] = int(address[1]) or 443
        try:
            s = socket.create_connection(address, timeout=self.timeout)
        except Exception as e:
            self.send_error(502)
            return
        self.send_response(200, 'Connection Established')
        self.end_headers()

        conns = [self.connection, s]
        self.close_connection = 0
        while not self.close_connection:
            rlist, wlist, xlist = select.select(conns, [], conns, self.timeout)
            if xlist or not rlist:
                break
            for r in rlist:
                other = conns[1] if r is conns[0] else conns[0]
                data = r.recv(8192)
                if not data:
                    self.close_connection = 1
                    break
                other.sendall(data)

    def do_GET(self):
        if self.path == 'http://proxy2.test/':
            self.send_cacert()
            return

        req = self
        content_length = int(req.headers.get('Content-Length', 0))
        req_body = self.rfile.read(content_length) if content_length else None

        if req.path[0] == '/':
            if isinstance(self.connection, ssl.SSLSocket):
                req.path = "https://%s%s" % (req.headers['Host'], req.path)
            else:
                req.path = "http://%s%s" % (req.headers['Host'], req.path)

        res = check_storage(req.headers['host'], req.path)
        if res is None:
            if debug:
                with self.lock:
                    print('Cache miss [%s] %s' % ('external' if self.allow_requests else 'aborted', req.path))
            if not self.allow_requests:
                self.send_error(404)                
                return
            req_body_modified = self.request_handler(req, req_body)
            if req_body_modified is not None:
                req_body = req_body_modified
                req.headers['Content-length'] = str(len(req_body))

            u = urllib.parse.urlsplit(req.path)
            scheme, netloc, path = u.scheme, u.netloc, (u.path + '?' + u.query if u.query else u.path)
            assert scheme in ('http', 'https')
            if netloc:
                req.headers['Host'] = netloc
            req_headers = filter_headers(req.headers)

            try:
                origin = (scheme, netloc)
                if not origin in self.tls.conns:
                    if scheme == 'https':
                        self.tls.conns[origin] = http.client.HTTPSConnection(netloc, timeout=self.timeout)
                    else:
                        self.tls.conns[origin] = http.client.HTTPConnection(netloc, timeout=self.timeout)
                conn = self.tls.conns[origin]
                conn.request(self.command, path, req_body, dict(req_headers))
                res = conn.getresponse()
            except Exception as e:
                if origin in self.tls.conns:
                    del self.tls.conns[origin]
                self.send_error(502)
                return
        else:
            if debug:
                with self.lock:
                    print('Cache hit %s' % req.path)

        res_body, res_body_plain, content_encoding = get_plain_resp(res)
        res_body_modified = self.response_handler(req, req_body, res, res_body_plain)
        if res_body_modified is not None:
            res_body_plain = res_body_modified
            res_body = self.encode_content_body(res_body_plain, content_encoding)
            res.headers['Content-Length'] = str(len(res_body))

        res_headers = filter_headers(res.headers)

        self.wfile.write(("%s %d %s\r\n" % (self.protocol_version, res.status, res.reason)).encode())
        head = headers_dict_to_str(res_headers)
        self.wfile.write(head.encode())
        self.wfile.write(b"\r\n")
        self.wfile.write(res_body)
        self.wfile.flush()

        with self.lock:
            self.save_handler(req, req_body, res, res_body_plain)

    do_HEAD = do_GET
    do_POST = do_GET
    do_OPTIONS = do_GET

    '''
    def send_cacert(self):
        with open(self.cacert, 'rb') as f:
            data = f.read()

        self.wfile.write("%s %d %s\r\n" % (self.protocol_version, 200, 'OK'))
        self.send_header('Content-Type', 'application/x-x509-ca-cert')
        self.send_header('Content-Length', len(data))
        self.send_header('Connection', 'close')
        self.end_headers()
        self.wfile.write(data)

    def print_info(self, req, req_body, res, res_body):
        def parse_qsl(s):
            return '\n'.join("%-20s %s" % (k, v) for k, v in urllib.parse.parse_qsl(s, keep_blank_values=True))

        req_header_text = "%s %s %s\n%s" % (req.command, req.path, req.request_version, req.headers)
        res_header_text = "%s %d %s\n%s" % (res.response_version, res.status, res.reason, res.headers)

        print(with_color(33, req_header_text))

        u = urllib.parse.urlsplit(req.path)
        if u.query:
            query_text = parse_qsl(u.query)
            print(with_color(32, "==== QUERY PARAMETERS ====\n%s\n" % query_text))

        cookie = req.headers.get('Cookie', '')
        if cookie:
            cookie = parse_qsl(re.sub(r';\s*', '&', cookie))
            print(with_color(32, "==== COOKIE ====\n%s\n" % cookie))

        auth = req.headers.get('Authorization', '')
        if auth.lower().startswith('basic'):
            token = auth.split()[1].decode('base64')
            print(with_color(31, "==== BASIC AUTH ====\n%s\n" % token))

        if req_body is not None:
            req_body_text = None
            content_type = req.headers.get('Content-Type', '')

            if content_type.startswith('application/x-www-form-urlencoded'):
                req_body_text = parse_qsl(req_body)
            elif content_type.startswith('application/json'):
                try:
                    json_obj = json.loads(req_body)
                    json_str = json.dumps(json_obj, indent=2)
                    if json_str.count('\n') < 50:
                        req_body_text = json_str
                    else:
                        lines = json_str.splitlines()
                        req_body_text = "%s\n(%d lines)" % ('\n'.join(lines[:50]), len(lines))
                except ValueError:
                    req_body_text = req_body
            elif len(req_body) < 1024:
                req_body_text = req_body

            if req_body_text:
                print(with_color(32, "==== REQUEST BODY ====\n%s\n" % req_body_text))

        print(with_color(36, res_header_text))

        cookies = res.headers.getheaders('Set-Cookie')
        if cookies:
            cookies = '\n'.join(cookies)
            print(with_color(31, "==== SET-COOKIE ====\n%s\n" % cookies))

        if res_body is not None:
            res_body_text = None
            content_type = res.headers.get('Content-Type', '')

            if content_type.startswith('application/json'):
                try:
                    json_obj = json.loads(res_body)
                    json_str = json.dumps(json_obj, indent=2)
                    if json_str.count('\n') < 50:
                        res_body_text = json_str
                    else:
                        lines = json_str.splitlines()
                        res_body_text = "%s\n(%d lines)" % ('\n'.join(lines[:50]), len(lines))
                except ValueError:
                    res_body_text = res_body
            elif content_type.startswith('text/html'):
                m = re.search(r'<title[^>]*>\s*([^<]+?)\s*</title>', res_body, re.I)
                if m:
                    h = HTMLParser()
                    print(with_color(32, "==== HTML TITLE ====\n%s\n" % h.unescape(m.group(1).decode('utf-8'))))
            elif content_type.startswith('text/') and len(res_body) < 1024:
                res_body_text = res_body

            if res_body_text:
                print(with_color(32, "==== RESPONSE BODY ====\n%s\n" % res_body_text))
    '''

    def request_handler(self, req, req_body):
        pass

    def response_handler(self, req, req_body, res, res_body):
        pass

    def save_handler(self, req, req_body, res, res_body):
        #self.print_info(req, req_body, res, res_body)
        pass

def test(HandlerClass=ProxyRequestHandler, ServerClass=ThreadingHTTPServer, protocol="HTTP/1.1"):
    if sys.argv[1:]:
        port = int(sys.argv[1])
    else:
        port = 8080
    server_address = ('', port)

    HandlerClass.protocol_version = protocol
    httpd = ServerClass(server_address, HandlerClass)

    sa = httpd.socket.getsockname()
    print("Serving HTTP Proxy on", sa[0], "port", sa[1], "...")
    httpd.serve_forever()


if __name__ == '__main__':
    test()
