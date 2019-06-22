import cherrypy
import os

class Search:
    def __init__(self):
        self.items = Item()
    def _cp_dispatch(self, vpath):
        return self.items.item

    @cherrypy.expose
    def index(self,q=None):
        return open('static/index.html').read()

class Item:
    @cherrypy.expose
    def item(self):
        return open('static/item.html').read()

config = {
	'global': {
		'server.socket_host': '0.0.0.0',
		'server.socket_port': int(os.environ.get('PORT', 5000)),
		'log.error_file': 'host.log',
	},
	'/static': {
		'tools.staticdir.root': os.getcwd(),
		'tools.staticdir.on': True,
		'tools.staticdir.dir': "static",
	},
	'/': {
        'tools.trailing_slash.on': False,
	},
}
if os.path.exists('hosts.log'):
    os.remove('host.log')
app = cherrypy.quickstart( Search(), config = config )
