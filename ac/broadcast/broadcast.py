import wss
import asyncio
import traceback
import sys

'''
WSS 广播 by sheepy 2020.8.28
'''


def wss_broadcast(port, sslKey, sslCert, sslDebug,  func, inter=0.1):
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    loop = asyncio.get_event_loop()
    server = wss.Server(port=port, debug=sslDebug, useSsl=True,
                        sslCert=sslCert, sslKey=sslKey)

    @asyncio.coroutine
    def sendData():
        while True:
            try:
                to_send = str(server.hasClients()) + "-!-" + func().replace('\'', '\"')
                # print("to_send:%s" % to_send)
                server.broadcast(to_send, False)
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
                traceback.print_exception(exc_type, exc_value, exc_traceback,
                                          limit=2, file=sys.stdout)
            yield from asyncio.sleep(float(inter), loop)

    try:
        server.start()
        print("\nWebsockets sevice enabled...")
    except:
        exc_type, exc_value, exc_traceback = sys.exc_info()
        traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
        traceback.print_exception(exc_type, exc_value, exc_traceback,
                                  limit=2, file=sys.stdout)

    loop.create_task(sendData())
    loop.run_forever()

