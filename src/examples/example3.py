from trabant import HTTPServer, loop
from bottle import route, app

@route('/ciao/:name')
def ciao(name):
    return 'hello ', name

@route('/')
def root():
    return 'hello from root'

server = HTTPServer(app(), 'localhost', 8080)

if __name__ == '__main__':
    loop()

