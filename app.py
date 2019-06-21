import cherrypy
import os

class Root:
    @cherrypy.expose
    def index(self):
        return open('public/index.html').read()
        
    index_shtml = index_html = index_htm = index_php = index

config = {
	'global': {
		'server.socket_host': '0.0.0.0',
		'server.socket_port': int(os.environ.get('PORT', 5000)),
		'log.error_file': 'host.log',
	},
	'/': {
		'tools.staticdir.root': os.getcwd(),
		'tools.staticdir.on': True,
		'tools.staticdir.dir': "public",
	},
}
        
app = cherrypy.quickstart( Root(), config = config )
