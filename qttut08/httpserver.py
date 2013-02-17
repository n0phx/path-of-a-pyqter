# -*- coding: utf-8 -*-
import time
import cgi
import httplib
import multiprocessing

from urlparse import parse_qs
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler


class TestHTTPRequestHandler(BaseHTTPRequestHandler):

    def __return_result(self):
        # 0.1 magic value, adds a minimum delay before returning a  response
        delay = 0.1 + self.server.context.get('delay', 0)
        time.sleep(delay)

        response = self.server.context.get('response', None)
        if response is not None:
            self.send_response(response)

        for name, value in self.server.context.get('headers', {}).items():
            self.send_header(name, value)

        self.end_headers()

        response_data = self.server.context.get('response_data', None)
        if response_data is not None:
            self.wfile.write(response_data)

    def do_GET(self):
        return self.__return_result()

    def do_POST(self):
        try:
            raw_content_type = self.headers.getheader('Content-type')
            content_type, _pdict = cgi.parse_header(raw_content_type)

            raw_content_length = self.headers.getheader('Content-length')
            content_length, _pdict = cgi.parse_header(raw_content_length)
            raw_data = parse_qs(self.rfile.read(int(content_length)))

            #print 'Content-type:', content_type
            #print 'Content-length:', content_length
            #print 'POST data:'
            #print raw_data
        except Exception as exc:
            print 'POST Handling failed: {0}'.format(str(exc))

        return self.__return_result()


class TestHTTPServer(HTTPServer):

    def __init__(self, context, *args, **kwargs):
        HTTPServer.__init__(self, *args, **kwargs)
        self.context = context


class ServerProcess(multiprocessing.Process):

    def __init__(self, address, port, context):
        multiprocessing.Process.__init__(self)
        self.address = address
        self.port = port
        self.context = context
        self.exit = multiprocessing.Event()

    def shutdown(self):
        self.exit.set()
        conn = httplib.HTTPConnection(self.address, self.port)
        conn.connect()
        conn.close()

    def run(self):
        TestHTTPRequestHandler.protocol_version = "HTTP/1.0"
        server = TestHTTPServer(self.context,
                                (self.address, self.port),
                                TestHTTPRequestHandler)

        sa = server.socket.getsockname()
        print "Serving HTTP on", sa[0], "port", sa[1], "..."

        while not self.exit.is_set():
            server.handle_request()
