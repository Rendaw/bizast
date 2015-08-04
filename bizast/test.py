from twisted.internet import reactor
from twisted.python import log
from kademlia.network import Server
import sys

# log to std out
log.startLogging(sys.stdout)

server = Server()
def quit(result):
    print "Key result:", result
    reactor.stop()

def get(result):
    return server.get("a key").addCallback(quit)

def done():
    #log.msg("Found nodes: %s" % found)
    return server.set("a key", "a value").addCallback(get)

server.listen(5678)

reactor.callWhenRunning(done)
reactor.run()
