import wss
import asyncio
import traceback
'''
WSS 广播 by sheepy 2020.8.28
'''


def wss_broadcast(port, sslKey, sslCert, sslDebug,  func, inter=0.3):
    new_loop = asyncio.new_event_loop()
    asyncio.set_event_loop(new_loop)
    loop = asyncio.get_event_loop()
    server = wss.Server(port=port, debug=sslDebug, useSsl=True,
                        sslCert=sslCert, sslKey=sslKey)

    @asyncio.coroutine
    def sendData():
        while True:
            try:
                to_send = func()
                server.broadcast(to_send, False)
            except:
                exc_type, exc_value, exc_traceback = sys.exc_info()
                traceback.print_tb(exc_traceback, limit=1, file=sys.stdout)
                traceback.print_exception(exc_type, exc_value, exc_traceback,
                                          limit=2, file=sys.stdout)
            yield from asyncio.sleep(inter)

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


def checkConfig(config):
    configkeys = config.keys()
    if "wss_port" in configkeys and "sslKey" in configkeys and "sslCert" in configkeys:
        if "sslDebug" in configkeys:
            sslDebug = True
        else:
            sslDebug = False
        if "wss_inter" in configkeys:
            wss_inter = float(config['wss_inter'])
            if wss_inter < 0.1:
                wss_inter = 0.1
        else:
            wss_inter = 0.3

        return [True, sslDebug, wss_inter]
    else:
        return False
