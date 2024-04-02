from trabant import Template, serve_static, App

def root(environ):
    return 'hello from root'

def ciao(environ, name):
    t = Template('Hello {{name}}!')
    return t.render(name=name)

routes = {
    '^/$': root,
    '^/static/(?P<path>.*)$': serve_static('static'),
    '^/ciao/(?P<name>.+)$': ciao,
}

app = App(routes)


if __name__ == '__main__':
    from trabant import ThreadedWSGIServer
    server = ThreadedWSGIServer(app, 'localhost', 8080)
    server.run()

