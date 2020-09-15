#!/usr/bin/env python
import os
import autobahn
import sys
import requests
import json
from broadcast import broadcast
import threading
from acplugins4python.ac_server_protocol import *
from acplugins4python.ac_server_plugin import *
from lib.mylib import *

playersDict = {}
NOTIME = 0


def callback(event):
    global sessionInfo
    if type(event) in [NewSession, SessionInfo]:
        sessionInfo = event
        print("NewSession:")
        # s.enableRealtimeReport(1000)
        # access the event data with
        # event.name, event.laps, etc. see the ac_server_protocol.py for the event definitions
        # in this example we print all available attributes of the received events
    elif type(event) == CarInfo:
        handle_car_info(event)
    elif type(event) == CarUpdate:
        handle_car_update(event)
    elif type(event) == NewConnection:
        print("NewConnection")
        handle_NewConnection(event)
    elif type(event) == ConnectionClosed:
        print("ConnectionClosed")
        handle_ConnectionClosed(event)
    elif type(event) == LapCompleted:
        print("LapCompleted")
        handle_lap_completed(event)
    elif type(event) == EndSession:
        print("EndSession")
    elif type(event) == ClientLoaded:
        print("ClientLoaded")
    elif type(event) == ProtocolError:
        print("ProtocolError")
    else:
        print("<unknown event>", type(event))
    # print("playersDict %s %s" % (playersDict.keys(), time.time()))


def handle_NewConnection(event):
    print_event(event)
    global playersDict
    carId = int(event.carId)
    if carId not in playersDict:
        player = Player(carId)
        t = get_player_dhq_info(event.driverGuid).split("|")
        player.cname = t[0]
        player.dhq_plyname = t[1]
        player.uid = t[2]
    else:
        player = playersDict[carId]
    player.carId = carId
    player.mDriverName = event.driverName
    player.guid = event.driverGuid
    player.car = event.carModel
    # print(player)
    playersDict[carId] = player


def handle_car_info(event):
    global playersDict
    carId = int(event.carId)
    if event.isConnected is True:
        handle_NewConnection(event)  # 如果已经连接则检查是否已在playersDict里，这一步和newConnet一样，故直接调用后者
    elif carId in playersDict:
        del playersDict[carId]


def handle_ConnectionClosed(event):
    global playersDict
    carId = int(event.carId)
    if carId in playersDict:
        # playersDict[carId].isConnected = False
        del playersDict[carId]


def handle_lap_completed(event):
    global playersDict, s
    carId = int(event.carId)
    if carId in playersDict:
        player = playersDict[carId]
        player.mLastLapTime = event.lapTime / 1000
        if 0 < player.mLastLapTime < player.mBestLapTime:
            player.mBestLapTime = player.mLastLapTime
        player.mCurSector1 = player.mCurSector2 = player.mCurSector3 = NOTIME
        lb_str = ""
        for i in event.leaderboard:
            lb_str = lb_str + "-" + str(i)

        # player.leaderboard = lb_str
        playersDict[carId] = player
    else:
        print("CarId:%s is not ready yet,try to get carInfo" % carId)
        s.getCarInfo(carId)
        s.processServerPackets(1)


def handle_car_update(event):
    carId = int(event.carId)
    if carId in playersDict:
        playersDict[carId].mPos_X = 0 - float(event.worldPos[2])
        playersDict[carId].mPos_Y = float(event.worldPos[0])
        playersDict[carId].mLocalVel_X = float(event.velocity[2])
        playersDict[carId].mLocalVel_Y = float(event.velocity[0])
        playersDict[carId].normalizedSplinePos = event.normalizedSplinePos

    if ini['Output_split_time'] == 1:
        logObj = ServerLogHandle(logFile)
        logLineCount = logObj.countLines() - 1
        refreshMode = True
        lastRead = int(ini['Last_read'])
        while lastRead <= logLineCount:
            print("\rLog已读取" + str(lastRead) + "\\" + str(logLineCount), end="")
            linedata = logObj.getLine(lastRead, refreshMode)
            if refreshMode:
                refreshMode = False
            # print(linedata)
            check_line(linedata)
            lastRead += 1
        logObj.close()
        try:
            iniObj.set("Last_read", str(lastRead))
        except Exception:
            traceback.print_exc()


class Player:
    def __init__(self, carId, plyname="", dhq_plyname="", uid=0, cname="", guid=0, car="", s1=NOTIME, s2=NOTIME,
                 s3=NOTIME, lastLapTime=NOTIME,
                 bestLapTime=9999999, laps=0, mPos_X=0, mPos_Y=0, mLocalVel_X=0, mLocalVel_Y=0, normalizedSplinePos = 0):
        self.carId = carId
        self.mDriverName = plyname  # 玩家在游戏里的名字
        self.dhq_plyname = dhq_plyname  # 玩家在dhq数据库里的名字
        self.uid = uid
        self.cname = cname
        self.guid = guid
        self.car = car
        self.mCurSector1 = s1
        self.mCurSector2 = s2
        self.mCurSector3 = s3
        self.mLastLapTime = lastLapTime
        self.mBestLapTime = bestLapTime
        self.laps = laps
        self.mPos_X = mPos_X
        self.mPos_Y = mPos_Y
        self.mLocalVel_X = mLocalVel_X
        self.mLocalVel_Y = mLocalVel_Y
        self.normalizedSplinePos = normalizedSplinePos


def get_lastest_file(path):
    dirs = os.listdir(path)
    fileDict = {}
    for filename in dirs:
        fullPath = os.path.join(path, filename)
        mtime = int(os.stat(fullPath).st_mtime)
        fileDict[mtime] = fullPath
    key = sorted(fileDict.keys())[-1]
    if int(time.time()) - key > 120:
        print("Log文件 %s 太老，是否未用BAT模式开启AC Server?" % str(fileDict[key]))
        input("按回车键退出")
        sys.exit(0)
    else:
        return fileDict[key]


def check_line(linedata):
    global playersDict, lastRead
    if linedata.find("Car.onSplitCompleted") > -1:
        print("\nlinedata:%s" % linedata)
        data = linedata.split(" ")
        carId = int(data[1])
        splitTime = int(data[3]) / 1000
        if carId in playersDict:
            player = playersDict[carId]
            if player.mCurSector1 == NOTIME:
                player.mCurSector1 = splitTime
                player.mCurSector2 = NOTIME
                player.mCurSector3 = NOTIME
            elif player.mCurSector2 == NOTIME:
                player.mCurSector2 = splitTime
                player.mCurSector3 = NOTIME
            elif player.mCurSector3 == NOTIME:
                player.mCurSector3 = splitTime
            playersDict[carId] = player


def getJson():
    playersDictForJson = {}
    for carId in playersDict:
        playersDictForJson[carId] = playersDict[carId].__dict__
    data = {"mVehicles": playersDictForJson}
    try:
        jsonStr = json.dumps(data, ensure_ascii=False)
        return jsonStr
    except Exception:
        traceback.print_exc()
        input()
        sys.exit(0)


def get_player_dhq_info(guid):
    re = requests.get("https://www.srfcworld.com/app/get_cname/%s" % guid).text.strip()
    return re


def get_ac_cfg(cfg):
    config = configparser.ConfigParser()
    try:
        config.read(cfg)
        return config['SERVER']
    except Exception:
        traceback.print_exc()
        input()
        sys.exit(0)


def main_udp_watcher(s):
    while True:
        s.processServerPackets()


def main():
    global s
    s = ACServerPlugin(rcvPort, sendPort, callback)
    # print("Get session info for current session")
    # s.getSessionInfo()
    # s.processServerPackets(0)
    # print("Get car info")
    for i in range(maxPlayer):
        print("\rGet car info %s,please wait..." % i, end="")
        s.getCarInfo(i)
        s.processServerPackets(1)
    s.enableRealtimeReport(100)
    s.processServerPackets(0)

    t1 = threading.Thread(target=broadcast.wss_broadcast,
                          args=(ini['wss_port'], ini['sslKey'], ini['sslCert'],
                                ini['sslDebug'], getJson, ini['wss_inter']))
    # 第5个参数是具体获得数据的函数名，比如get_ac_ws_data
    t2 = threading.Thread(target=main_udp_watcher, args=(s,))
    try:
        t1.start()
        t2.start()
    except Exception as e:
        print("error on thread")
        errorHandle(e)


if __name__ == "__main__":
    print("SRFC AC SERVER UDP TRACKER 0.5\n\n")
    s = ""
    iniObj = IniHandle()
    ini = iniObj.read()
    lastRead = int(ini['Last_read'])  # 上次读到第几行
    ACPath = ini['AC_path']
    logPath = ACPath + "logs/session/"
    ac_cfg = get_ac_cfg(ACPath + "cfg/server_cfg.ini")
    print("Server:" + ac_cfg['NAME'])
    maxPlayer = int(ac_cfg['MAX_CLIENTS'])
    print("Max player:" + str(maxPlayer))

    rcvPort = int(ini['UDP_PLUGIN_ADDRESS'])
    sendPort = int(ini['UDP_PLUGIN_LOCAL_PORT'])
    if ini['Output_split_time'] == 1:
        logFile = get_lastest_file(logPath)
        logObj = ServerLogHandle(logFile)
        lastlogLineCount = logObj.countLines() - 1
        print("Log:%s" % logFile)
        print("Log line:" + str(lastlogLineCount))
        print("Last Read:" + str(lastRead))
    else:
        print("Split time output not available.")

    try:
        main()
    except Exception as e:
        errorHandle("main error！")
