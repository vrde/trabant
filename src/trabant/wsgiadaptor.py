import re
import os
import cgi
import mimetypes
import traceback
from trabant import utils
try:
    from resources import opener
except ImportError:
    import warnings
    warnings.warn("Unable to load module `resources`, Trabant will be "
            "unable to load static resources contained in zip file")
    opener = open


STATUS_CODES = {
    200: 'OK',
    302: 'Found',
    304: 'Not Modified',
    404: 'Not Found',
    418: 'I\'m a teapot',
    500: 'Internal Server Error',
}

class HTTPError(Exception):
    def __init__(self, status_code):
        self.status_code = status_code

class HTTPRedirect(HTTPError):
    def __init__(self, status_code, location):
        self.status_code = status_code
        self.location = location

def serve_static(base='', module=None):
    def _serve_static(environ, path):
        if 'HTTP_IF_MODIFIED_SINCE' in environ:
            raise HTTPError(304)

        guessed_type = mimetypes.guess_type(path)
        if guessed_type[0] is None:
            mime_type = 'text/plain'
        else:
            if guessed_type[1] is None:
                mime_type = guessed_type[0]
                if mime_type == 'image/x-png':
                    mime_type = 'image/png'
            else:
                mime_type = ';charset='.join(guessed_type)

        if module:
            f = opener(os.path.join(base, path), 'r', module=module)
        else:
            f = opener(os.path.join(base, path), 'r')

        #if not abspath.startswith('.'):
        #    raise HTTPError(404)

        try:
            return [ ('Content-Type', mime_type),
                    # %a, %d %b %Y %H:%M:%S
                    ('Last-Modified', 'Tue, 17 Apr 2012 00:00:00') ], f.read()
        except IOError:
            raise HTTPError(404)
    return _serve_static

def redirect(environ, location):
    raise HTTPRedirect(302, location)


class App(object):

    def __init__(self, routes):
        self.routes = routes

    def __call__(self, environ, start_response):
        status = '200 OK'
        for pattern, func in self.routes.items():
            match = re.search(pattern, environ['PATH_INFO'])
            if match:
                break
        headers = [('Content-type', 'text/html')]
        body = ''
        try:
            if not match:
                raise HTTPError(404)

            environ['trabant.params'] = utils.parse_params(environ['QUERY_STRING'])
            if environ['REQUEST_METHOD'] == 'POST':
                moar = cgi.parse(environ['wsgi.input'], environ)
                environ['trabant.params'].update(moar)
            result = func(environ, **match.groupdict())
            if isinstance(result, tuple):
                headers, body = result
            else:
                body = result

        except HTTPRedirect, e:
            status = '%d %s' % (e.status_code, STATUS_CODES[e.status_code])
            headers = [('Location', e.location)]
            body = ''

        except HTTPError, e:
            status = '%d %s' % (e.status_code, STATUS_CODES[e.status_code])
            body = status

        except Exception, e:
            status = '500 Server Error'
            body = '<h1>Ouch... Internal Server Error</h1>\n<pre>%s</pre>' % traceback.format_exc()

        start_response(status, headers)
        #FIXME: this will make pandas sad :(
        return [body]

