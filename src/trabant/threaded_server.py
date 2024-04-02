# -*- coding: utf-8 -*-
"""
    James WSGI Server
    =================
    
    [James][1] provides a very simple multi-threaded [WSGI][2] server
    implementation based on the HTTPServer from Python's standard library.
    
    You can host multiple applications on one host as well as static files.
    
    **Important** - James is is a simple server for use in testing or
    debugging WSGI applications. It hasn't been reviewed for security
    issues. Don't use it for production use.
    
    Use it for demo and debugging purposes.
    
    
    Basic Example
    -------------
    You can add a James call using the `__name__` hook on the bottom of
    your application file:
    
        if __name__ == '__main__':
            from james import WSGIServer
            WSGIServer(applications={'/': my_application}).run()
    
    This example assumes that your application is named `my_application`.
    Your application will be mounted on `/`. Using the `applications`
    parameter you can install more than one application on the same james
    server.
    
    
    Serving Static Files
    --------------------
    James can also handle static files. For this purpose it takes a
    parameter `files`:
    
        if __name__ == '__main__':
            from os import path
            from james import WSGIServer
            base = path.dirname(__file__) + '/static'
            
            WSGIServer(
                applications={
                    '/': my_application
                },
                files={
                    '/favicon.ico':         base + '/favicon.ico',
                    '/css':                 base + '/css',
                    '/img':                 base + '/img'
                }
            ).run()
    
    
    Defining Hostname and Port
    --------------------------
    Per default James listens on [localhost][3] Port 8080.
    
    To change this behavior you can use the parameters `hostname` and
    `port`:
    
        if __name__ == '__main__':
            from james import WSGIServer
            WSGIServer(hostname='mycomputername', port=80,
                       applications={'/': myapplication}).run()
                       
    
    [1]: http://wsgiarea.pocoo.org/james/
    [2]: http://www.python.org/peps/pep-0333.html
    [3]: http://localhost:8080/
"""

__author__ = 'Armin Ronacher <armin.ronacher@active-4.com>'
__version__ = '0.7.1'
__license__ = 'GNU General Public License (GPL)'

#from __future__ import generators
from SocketServer import ThreadingMixIn
from BaseHTTPServer import HTTPServer, BaseHTTPRequestHandler
from urlparse import urlparse
import threading
import socket
import mimetypes
import sys
import os


# XXX: http://bugs.python.org/issue6085
def _bare_address_string(self):
    host, port = self.client_address[:2]
    return '%s' % host

BaseHTTPRequestHandler.address_string = _bare_address_string


HTTP_ERROR_TEMPLATE = """<!DOCTYPE HTML PUBLIC "-//W3C//DTD HTML 3.2 Final//EN">
<html>
 <head>
  <title>%(title)s</title>
  <style type="text/css">
    body {
        font-family: sans-serif;
        margin: 2em;
        padding: 0;
    }
    a, h1 {
        color: #0000cc;
    }
    div.content {
        margin: 1em 3em 2em 2em;
    }
    address {
        border-top: 1px solid #ccc;
        padding: 0.3em;
    }
  </style>
 </head>
 <body>
<h1>%(title)s</h1>
<div class="content">%(content)s</div>
<address>powered by James %(versioninfo)s</address>
</body></html>"""


class WSGIHandler(BaseHTTPRequestHandler):

    def do_GET(self):
        self.call_handler()

    def do_POST(self):
        self.call_handler(True)

    def log_message(self, format, *args):
        pass

    def send_error(self, code, message):
        url = urlparse(self.path)[2]

        if code == 404:
            message = 'The requested URL %s was not found on this server.' % url
        pyversion = sys.version.split('\n')[0].strip()
        args = {
            'title': 'Error %i' % code,
            'content': message,
            'versioninfo': '%s - Python %s' % (__version__, pyversion)
        }
        self.send_response(code, message)
        self.send_header('Content-Type', 'text/html')
        self.send_header('Connection', 'close')
        self.end_headers()
        if self.command != 'HEAD' and code >= 200 and code not in (204, 304):
            self.wfile.write(HTTP_ERROR_TEMPLATE % args)

    def call_handler(self, skip_files=False):
        path_info, parameters, query = urlparse(self.path)[2:5]
        #if path_info[-1] != '/':
        #    path_info += '/'

        # First check for files
        if not skip_files:
            for search_path, file_path in self.server.files.items():
                if search_path[:-1] != '/':
                    search_path += '/'
                if path_info.startswith(search_path):
                    real_path = os.path.join(file_path, path_info[len(search_path):])
                    if os.path.exists(real_path) and os.path.isfile(real_path):
                        return self.serve_file(real_path)
                    self.send_error(404, 'File not found')
                    return

        # Not check for applications
        path = path_info
        for search_path, app in self.server.applications.items():
            if path.startswith(search_path):
                path_info = path[len(search_path):]
                #if path_info and not path_info.startswith('/'):
                if not path_info.startswith('/'):
                    path_info = '/' + path_info
                if search_path.endswith('/'):
                    script_name = search_path[:-1]
                else:
                    script_name = search_path
                return self.run_application(app, path_info, script_name, query)

        self.send_error(404, 'Application not found')


    def serve_file(self, filename):
        guessed_type = mimetypes.guess_type(filename)
        if guessed_type[0] is None:
            mime_type = 'text/plain'
        else:
            if guessed_type[1] is None:
                mime_type = guessed_type[0]
            else:
                mime_type = ';charset='.join(guessed_type)
            self.send_response(200, 'OK')
            self.send_header('Content-Type', mime_type)
            self.end_headers()
            for line in file(filename):
                self.wfile.write(line)


    def run_application(self, app, path_info, script_name, query):
        environ = {
            'wsgi.version':         (1,0),
            'wsgi.url_scheme':      'http',
            'wsgi.input':           self.rfile,
            'wsgi.errors':          sys.stderr,
            'wsgi.multithread':     1,
            'wsgi.multiprocess':    0,
            'wsgi.run_once':        0,
            'trabant.stop':         self.server.stop,
            'REQUEST_METHOD':       self.command,
            'SCRIPT_NAME':          script_name,
            'QUERY_STRING':         query,
            'CONTENT_TYPE':         self.headers.get('Content-Type', ''),
            'CONTENT_LENGTH':       self.headers.get('Content-Length', ''),
            'REMOTE_ADDR':          self.client_address[0],
            'REMOTE_PORT':          self.client_address[1],
            'SERVER_NAME':          self.server.server_address[0],
            'SERVER_POST':          self.server.server_address[1],
            'SERVER_PROTOCOL':      self.request_version
        }
        if path_info:
            from urllib import unquote
            environ['PATH_INFO'] = unquote(path_info)
        for key, value in self.headers.items():
            environ['HTTP_' + key.upper().replace('-', '_')] = value

        headers_set = []
        headers_sent = []

        def write(data):
            if not headers_set:
                raise AssertionError, 'write() before start_response'

            elif not headers_sent:
                status, response_headers = headers_sent[:] = headers_set
                code, msg = status.split(' ', 1)
                self.send_response(int(code), msg)
                for line in response_headers:
                    self.send_header(*line)
                self.end_headers()

            self.wfile.write(data)

        def start_response(status, response_headers, exc_info=None):
            if exc_info:
                try:
                    if headers_sent:
                        raise exc_info[0], exc_info[1], exc_info[2]
                finally:
                    exc_info = None
            elif headers_set:
                raise AssertionError, 'Headers already set!'

            headers_set[:] = [status, response_headers]
            return write

        result = app(environ, start_response)
        try:
            try:
                for data in result:
                    write(data)
            finally:
                if hasattr(result, 'close'):
                    result.close()
        except (socket.error, socket.timeout):
            return # "there was no error" ^^


class WSGIServer(HTTPServer):

    def __init__(self, app, hostname='localhost', port=8080, files={}):
        HTTPServer.__init__(self, (hostname, port), WSGIHandler)
        if isinstance(app, dict):
            self.applications = app
        else:
            self.applications = {'/': app}
        self.files = files
        self.running = True

    def run(self):
        while self.running:
            self.handle_request()

    def stop(self):
        self.running = False

    def serve_forever(self):
        raise NotImplementedError


class ThreadedWSGIServer(ThreadingMixIn, WSGIServer):
    pass

