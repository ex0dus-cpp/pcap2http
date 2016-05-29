Pcap2http
=========
Parse and show HTTP sites. Python 3.3+ required.

This module parses pcap(ng) files, retrieves HTTP data, and gives you the opportunity to see it in your browser or in the file system. Pcap files can be obtained via tcpdump or wireshark or other network traffic capture tools.

Features
========

* HTTP requests/responses grouped by TCP connections; the requests in one keep-alive http connection will display together.
* Managed chunked and compressed HTTP requests/responses.
* Managed character encoding
* Display the site hierarchy, the contents of which were stored in pcap (ng) format.
* Dump content of sites to the file system with preserving the directory structure.
* Start the HTTP-Proxy with allows you to view the contents of the intercepted sites in the browser.
* Integration with Wireshark via Lua plugin.

Install
=======
::

    pip install pcap2http
    
Examples
========

Start the HTTP-Proxy on port 8337, wait for connections to the proxy (that returns contents of all detected url address)
::

    python3 pcap2http.py dump.pcap

Filter HTTP-packets for domain domain.com, start the HTTP-proxy on port 8337, wait for connections to the proxy (that returns contents of all detected url addresses of domain.com website )
::

    python3 pcap2http.py --domain domain.com dump.pcap

Filter HTTP-packets for domain domain.com, start the HTTP-proxy on port 8337, wait for connections to the proxy (that returns contents of all detected url addresses of domain.com website, and forwards all other url to the internet (transparent proxy))
::

    python3 pcap2http.py --domain domain.com --allow-requests dump.pcap

Filter HTTP-packets on the URI "/api/update" pattern, show directory structure on the screen (in this case only domain.com website) and dump contents to the file system.
::

    python3 pcap2http.py --uri "/api/update" --print-tree --dump-tree dump.pcap

Filter HTTP-packets over ip 123.123.123.123, save data to the file "saved.bin"
::

    python3 pcap2http.py --ip "123.123.123.123" --save-storage saved.bin ololo.pcap

Start the HTTP-Proxy on port 8337, wait for connections to the proxy (that returns the contents of url addresses previously stored in "saved.bin" file)
::

    python3 pcap2http.py saved.bin
