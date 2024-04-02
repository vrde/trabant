import socket
import asyncore
import asynchat

from StringIO import StringIO
from datetime import datetime

from trabant import utils

SERVER = 'Trabant 0.0.1'

def httpdate(dt):
    """Return a string representation of a date according to RFC 1123
    (HTTP/1.1).

    The supplied date must be in UTC.

    """
    weekday = ['Mon', 'Tue', 'Wed', 'Thu', 'Fri', 'Sat', 'Sun'][dt.weekday()]
    month = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep',
             'Oct', 'Nov', 'Dec'][dt.month - 1]
    return '%s, %02d %s %04d %02d:%02d:%02d GMT' % (weekday, dt.day, month,
        dt.year, dt.hour, dt.minute, dt.second)

class RequestHandler(asynchat.async_chat):
    READING_HEADERS = 0
    READING_BODY_DATA = 1
    HANDLING = 2
    FINISHED = 3

    def __init__(self, sock, addr, server):
        asynchat.async_chat.__init__(self, sock)
        self.addr = addr
        self.server = server 
        self.ibuffer = StringIO()
        self.obuffer = ''
        self.set_terminator('\r\n\r\n')
        self.state = RequestHandler.READING_HEADERS
        self.cgi_data = None

    def _prepare_environ(self):
        environ = self.server.environ.copy()
        headers = {}
        args = {}
        self.ibuffer.seek(0)
        lines = filter(bool, self.ibuffer.readlines())
        method, url, protocol = lines.pop(0).split()
        path, query = utils.splitquery(url)

        environ['REQUEST_METHOD'] = method.upper()
        environ['SCRIPT_NAME'] = ''
        environ['PATH_INFO'] = path
        environ['QUERY_STRING'] = query
        environ['SERVER_PROTOCOL'] = protocol

        for line in lines:
            k, v = map(str.strip, line.split(':', 1))
            header = '_'.join(k.split('-')).upper()
            if header not in ('CONTENT_LENGTH', 'CONTENT_TYPE'):
                header = 'HTTP_%s' % header
            environ[header] = v
        self.ibuffer.seek(0, 2)
        return environ


    def collect_incoming_data(self, data):
        """Buffer the data"""
        if self.state == RequestHandler.READING_BODY_DATA:
            self.environ['wsgi.input'].write(data)
        else:
            self.ibuffer.write(data)

    def found_terminator(self):
        if self.state == RequestHandler.READING_HEADERS:
            self.environ = self._prepare_environ()
            if self.environ['REQUEST_METHOD'] == 'POST':
                self.state = RequestHandler.READING_BODY_DATA
                length = self.environ['CONTENT_LENGTH']
                expect = self.environ.get('HTTP_EXPECT')
                self.environ['wsgi.input'] = StringIO()
                if not expect:
                    self.obuffer.append('')
                    self.status = RequestHandler.FINISHED
                else:
                    self.obuffer = 'HTTP/1.1 100 Continue\r\n\r\n'

                self.set_terminator(int(length))
            else:
                self.state = RequestHandler.HANDLING
                self.set_terminator(None)
                self.handle_request()
        elif self.state == RequestHandler.READING_BODY_DATA:
            self.set_terminator(None) # browsers sometimes over-send
            self.environ['wsgi.input'].seek(0)
            self.handle_request()

    def readable(self):
        return self.state != RequestHandler.FINISHED

    def writable(self):
        return (len(self.obuffer) > 0)

    def handle_request(self):
        buffer = []
        def start_response(status, response_headers, exc_info=None):
            status_code = status[:3]
            buffer.append(' '.join((self.environ['SERVER_PROTOCOL'], status)))
            buffer.extend([': '.join(h) for h in response_headers])

        result = self.server.wsgiapp(self.environ, start_response)

        body = ''.join(result)
        buffer.extend([
            'Date: %s' % httpdate(datetime.utcnow()),
            'Server: %s' % SERVER,
            #'Accept-Ranges: none',
            'Connection: close',
        ])

        if body:
            buffer.extend(['Content-Length: %d' % len(body), '', body])

        self.obuffer = '\r\n'.join(buffer)
        self.state = RequestHandler.FINISHED

    def handle_expt(self):
        print 'exception!'
        self.close()

    def handle_write(self):
        sent = self.send(self.obuffer)
        self.obuffer = self.obuffer[sent:]
        if not self.obuffer and self.state == RequestHandler.FINISHED:
            self.close()


class HTTPServer(asyncore.dispatcher):

    def __init__(self, wsgiapp, host, port):
        asyncore.dispatcher.__init__(self)
        self.environ = {
            'trabant_server.close': self.close,
            'wsgi.errors': None,
            'wsgi.version': (1, 0),
            'wsgi.multithread': False,
            'wsgi.multiprocess': False,
            'wsgi.run_once': True,
            #FIXME:
            'SERVER_NAME': host,
            'SERVER_PORT': port,
        }
        self.wsgiapp = wsgiapp
        self.create_socket(socket.AF_INET, socket.SOCK_STREAM)
        self.set_reuse_addr()
        self.bind((host, port))
        self.listen(2)

    def handle_accept(self):
        pair = self.accept()
        if pair is None:
            pass
        else:
            sock, addr = pair
            handler = RequestHandler(sock, addr, self)

def loop():
    asyncore.loop()

