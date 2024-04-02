from paste import httpserver
from trabant import Template, App, serve_static

def root(environ):
    return 'hello from root'

def ciao(environ, name):
    t = Template('Hello {{name}}!')
    return t.render(name=name)

routes = {
    '^/$': root,
    '^/static/(?P<path>.*)$': serve_static,
    '^/ciao/(?P<name>.+)$': ciao,
}

app = App(routes)

if __name__ == '__main__':
    httpserver.serve(app)

