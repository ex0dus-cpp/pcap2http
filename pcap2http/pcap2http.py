from pcapparsermod import config
from pcapparsermod.parse_pcap import parse_pcap_file
import urllib
import argparse
import traceback
import proxy
from base64 import b64encode
import json
import pickle
import threading
import time
import re
import io
import os

def print_tree(tree, i=0):
    for key in sorted(tree.keys()):
        print('%s%s%s' % (' '.ljust(i * 2), '/' if i != 0 else '', key))
        if isinstance(tree[key], dict):
            print_tree(tree[key], i + 1)

def sanitize(s):
    if '?' in s:
        spl = s.split('?', 1)
        spl[1] = b64encode(('?' + spl[1]).encode()).decode()
        s = ''.join(spl)
    return s[:150]

def dump_tree(tree, path='./'):
    for key in sorted(tree.keys()):
        new_path = path + key
        #print(new_path)
        if isinstance(tree[key], dict):
            new_path += '/'
            try:
                os.mkdir(sanitize(new_path))
            except Exception:
                pass
            dump_tree(tree[key], new_path)
        else:
            res = proxy.get_response_from_storage(tree[key], key)
            res_body, res_body_plain, content_encoding = proxy.get_plain_resp(res)
            with open(sanitize(new_path), 'wb') as f:
                f.write(res_body_plain)

def get_tree_from_storage(storage):
    tree = dict()
    for host in storage:
        for path in storage[host]:
            full_url = host + path

            # a/b/c?d/e -> [a, b, c?d/e]
            splitted = full_url.split('?', 1)  # a/b/c?asd -> [a/b/c, asd]
            parts = splitted[0].split('/')  #
            if len(splitted) == 2: parts[-1] += '?' + splitted[1]

            # print(parts)
            # [a, b, c] -> {a: {b: {c: http}}}
            # [a, b, d] -> {a: {b: {c: http}, {d: http}}}
            ref = tree
            for i in range(len(parts)):
                if parts[i] == '':
                    parts[i] = 'index.html'

                # this is file
                if i == len(parts) - 1:
                    ref.setdefault(parts[i], storage[host][path])
                # this is folder
                else:
                    # if domain.com/ololo in tree, but now full_url=domain.com/ololo/
                    if parts[i] in ref and not isinstance(ref[parts[i]], dict):
                        ref.setdefault(parts[i] + '.html', ref[parts[i]])  # rename to domain.com/ololo.html
                        ref[parts[i]] = dict()  # and add folder domain.com/ololo/
                    if parts[i] not in ref:
                        ref.setdefault(parts[i], dict())
                    ref = ref[parts[i]]
    return tree

def run_browser(browser, url):
    time.sleep(2)
    os.system('"%s" %s' % (browser, url))

def get_url_from_packet(packet, storage):
    for host in storage:
        for path in storage[host]:
            head, body, numbers = storage[host][path]
            #print(host + path, numbers, packet in numbers)
            if packet in numbers:
                return host + path

def parse_args():
    parser = argparse.ArgumentParser()
    parser.add_argument("infile", help="the pcap(ng) file to parse or .bin file with saved by pickle storage")

    parser.add_argument("-i", "--ip", type=str, help="only parse packages with specified source OR dest ip")
    parser.add_argument("-p", "--port", type=int,
                        help="only parse packages with specified source OR dest port")
    parser.add_argument("-d", "--domain", type=str, help="filter http data by request domain")
    parser.add_argument("-u", "--uri", type=str, help="filter http data by request uri pattern")

    parser.add_argument("--debug", action='store_true', help="show debug information")
    parser.add_argument("--dump-tree", action='store_true', help="create tree of directories for every url in pcap")
    parser.add_argument("--print-tree", action='store_true', help="print tree of urls in console")
    parser.add_argument("--save-storage", type=str, metavar='name.bin', help="pickle storage into file")
    parser.add_argument("--allow-requests", action='store_true', help="allow proxy to make requests or show only from pcap file")

    parser.add_argument("-n", "--packet", type=int, help="filter http data by packet number in pcap")
    parser.add_argument("--browser", type=str, metavar='name.exe', help="open browser with url from --packet")
    return parser.parse_args()

def main():
    args = parse_args()

    _filter = config.get_filter()
    _filter.ip = args.ip
    _filter.port = args.port
    enc = lambda x: x.encode() if isinstance(x, str) else x
    _filter.domain = enc(args.domain)
    _filter.uri_pattern = enc(args.uri)

    with open(args.infile, 'rb') as fin:
        if args.infile.endswith('.bin'):
            storage = pickle.load(fin)
        else:
            storage = parse_pcap_file(fin)

    proxy.debug = args.debug
    proxy.storage = storage

    proxy.ProxyRequestHandler.protocol_version = 'HTTP/1.1'
    proxy.ProxyRequestHandler.allow_requests = args.allow_requests

    if args.save_storage:
        with open(args.save_storage, 'wb') as fout:
            pickle.dump(storage, fout)
        print('Storage saved into ' + args.save_storage)
    elif args.print_tree or args.dump_tree:
        tree = get_tree_from_storage(storage)
        if args.print_tree:
            print_tree(tree)
        if args.dump_tree:
            folder = './' + os.path.split(args.infile)[1].split('.')[0] + '/'
            os.system('rm -rf ' + folder)
            os.mkdir(folder)
            dump_tree(tree, folder)
            print('File tree dumped into folder ' + folder)
    else:
        httpd = proxy.ThreadingHTTPServer(('127.0.0.1', 8337), proxy.ProxyRequestHandler)
        print('Proxy started on 127.0.0.1:8337')
        if args.browser:
            url_from_packet = get_url_from_packet(args.packet, storage)
            th_args = (args.browser, url_from_packet)
            threading.Thread(target=run_browser, args=th_args, daemon=False).start()
        httpd.serve_forever()        

if __name__ == '__main__':
    main()