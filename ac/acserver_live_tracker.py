#!/usr/bin/env python
import os
import requests
import sys
import json
from broadcast import broadcast
import threading
from acplugins4python.ac_server_protocol import *
from acplugins4python.ac_server_plugin import *
from lib.mylib import *
from urllib3 import encode_multipart_formdata


playersDict = {}
NOTIME = 0
headers = {'user-agent': 'SRFC AC TRACKER/0.9'}


class Player:
    def __init__(self, carId, plyname="", dhq_plyname="", uid=0, cname="", guid=0, car="", s1=NOTIME, s2=NOTIME,
                 s3=NOTIME, lastLapTime=NOTIME, isConnected=False,
                 bestLapTime=9999999, mTotalLaps=0, mPos_X=0, mPos_Y=0, mLocalVel_X=0, mLocalVel_Y=0, normalizedSplinePos=0, leaderboard="", mPlace=99, cuts=0):
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
        self.mTotalLaps = mTotalLaps
        self.mPos_X = mPos_X
        self.mPos_Y = mPos_Y
        self.mLocalVel_X = mLocalVel_X
        self.mLocalVel_Y = mLocalVel_Y
        self.normalizedSplinePos = normalizedSplinePos
        self.leaderboard = leaderboard
        self.mPlace = mPlace
        self.isConnected = isConnected
        self.cuts = cuts


def callback(event):
    global sessionInfo, gInfo
    if type(event) in [NewSession, SessionInfo]:
        if sessionInfo != '':
            if event.sessionIndex != sessionInfo.sessionIndex:  # 如果新的sessionIndex和旧的不一样，代表进入了新session，重新读一下车辆信息
                handle_new_session()
        else:
            handle_new_session()
        sessionInfo = event
        # print(sessionInfo)  # elapsedMS  sessionType = 1 for practice  sessionTime = 120 (min)
        # handle_new_session()
        # s.enableRealtimeReport(1000)
        # access the event data with
        # event.name, event.laps, etc. see the ac_server_protocol.py for the event definitions
        # in this example we print all available attributes of the received events
    elif type(event) == CarInfo:
        handle_car_info(event)
    elif type(event) == CarUpdate:
        handle_car_update(event)
    elif type(event) == NewConnection:
        print("\n新连接")
        handle_NewConnection(event)
    elif type(event) == ConnectionClosed:
        print("\n连接关闭")
        handle_ConnectionClosed(event)
    elif type(event) == LapCompleted:
        print("\n完成了一圈")
        handle_lap_completed(event)
    elif type(event) == EndSession:
        print("\nEndSession")
    elif type(event) == ClientLoaded:
        print("\n客户加载完毕")
        gInfo = str(event.carId) + " loaded"
    elif type(event) == ProtocolError:
        print("ProtocolError")
    else:
        # print("<unknown event>", type(event))
        pass
    # print("playersDict %s %s" % (playersDict.keys(), time.time()))


def handle_new_session():
    global gInfo, latestResultFile
    gInfo = "New SESSION"
    if ini['daily'] == 1:
        resultFile = get_lastest_result_file(resultPath)
        url = "https://www.srfcworld.com/admin/result/daily_upload?sn=" + ini['sid'] + "&DEBUG=1"
        if resultFile != latestResultFile:
            try:
                data = {'file': ('acResult.json', open(resultFile, 'rb').read())}
                encode_data = encode_multipart_formdata(data)
                data = encode_data[0]
                header = {'Content-Type': encode_data[1]}
                r = requests.post(url, headers=header, data=data)
                print(r.content.decode('utf-8'))
                latestResultFile = resultFile
            except Exception:
                traceback.print_exc()
                sys.exit(0)
        else:
            print("\n成绩文件已经上传。")

    get_carInfo()  # 新session确保carId列表正确
    gen_onlineList()


def handle_NewConnection(event):
    global gInfo, playersDict
    # print_event(event)
    carId = int(event.carId)
    gInfo = "\n新连接，ID:" + str(carId)
    if carId not in playersDict:
        player = Player(carId)
    else:
        player = playersDict[carId]
    player.carId = carId
    player.mDriverName = event.driverName
    player.guid = event.driverGuid
    player.car = event.carModel
    player.isConnected = True
    # print(player)
    playersDict[carId] = player
    gen_onlineList()


def handle_car_info(event):
    global playersDict
    carId = int(event.carId)
    if event.isConnected is True:
        handle_NewConnection(event)  # 如果已经连接则检查是否已在playersDict里，这一步和newConnet一样，故直接调用后者
    elif carId in playersDict:
        del playersDict[carId]


def handle_ConnectionClosed(event):
    global gInfo, playersDict
    getSessionInfo()
    carId = int(event.carId)
    gInfo = "ID:" + str(carId) + " 断开连接"
    if carId in playersDict:
        # playersDict[carId].isConnected = False
        del playersDict[carId]
        gen_onlineList()


def handle_lap_completed(event):
    global s, gInfo, playersDict
    carId = int(event.carId)
    gInfo = "ID:" + str(carId) + " 完成了1圈"
    if carId in playersDict:
        player = playersDict[carId]
        player.mLastLapTime = event.lapTime / 1000
        player.cuts = event.cuts
        if 0 < player.mLastLapTime < player.mBestLapTime and not player.cuts:
            player.mBestLapTime = player.mLastLapTime
        j = 1
        for i in event.leaderboard:
            lb_str = str(i).replace("<class 'acplugins4python.ac_server_protocol.LeaderboardEntry'>", "")
            lb_str = lb_str.replace("(", "").replace(")", "")  # carId=12, lapTime=75182, laps=13, completed=0,
            temp = lb_str.split(",")
            tempCarId = int(temp[0][6:])
            # print("tempCarId:" + str(tempCarId))
            if tempCarId in playersDict:
                playersDict[tempCarId].mTotalLaps = temp[2][6:]
                print(lb_str + " place:" + str(j) + " laps:" + temp[2][6:])
                playersDict[tempCarId].mPlace = j
            j += 1
        playersDict[carId] = player

        if event.cuts == 0:
            timestamp = int(time.time())
            laptime = int(event.lapTime)/1000
            data = "0,1,%s,%s,%s,5,6,7,8,%s,%f,%f,%f,%f,%f,%f,%i\n" \
                   % (player.guid, player.car, player.mDriverName, player.mTotalLaps, player.mCurSector1,
                      player.mCurSector2, laptime, player.mCurSector1, player.mCurSector2, laptime, timestamp)
            url = "https://www.srfcworld.com/misc/do_log?sn=%s&DEBUG=1" % ini['sid']
            do_post(data, url)
        else:
            print("CarId:%s laptime have %i cut(s)" % (carId, event.cuts))
    else:
        gInfo = "ID:" + str(carId) + " unknow,requiring"
        print("CarId:%s is not ready yet,try to get carInfo" % carId)
        s.getCarInfo(carId)
        s.processServerPackets(1)


def handle_car_update(event):
    global gInfo, s, lastRead
    carId = int(event.carId)
    if carId in playersDict:
        playersDict[carId].mPos_X = 0 - float(event.worldPos[2])
        playersDict[carId].mPos_Y = float(event.worldPos[0])
        playersDict[carId].mLocalVel_X = float(event.velocity[2])
        playersDict[carId].mLocalVel_Y = float(event.velocity[0])
        playersDict[carId].normalizedSplinePos = event.normalizedSplinePos
        gInfo = "ID:" + str(carId) + " update:(" + str(int(playersDict[carId].mPos_X)) + "," + str(int(playersDict[carId].mPos_Y)) + ")" + time.strftime("%H:%M:%S", time.localtime())
    else:
        gInfo = "ID:" + str(carId) + " unknow,requiring"
        print("CarId:%s is not ready yet,try to get carInfo" % carId)
        s.getCarInfo(carId)
        s.processServerPackets(1)

    if ini['Output_split_time'] == "1":
        logObj = ServerLogHandle(logFile)
        logLineCount = logObj.countLines() - 1
        refreshMode = True
        while lastRead <= logLineCount:
            print("\rLog已读取" + str(lastRead) + "\\" + str(logLineCount), end="")
            linedata = logObj.getLine(lastRead, refreshMode)
            if refreshMode:
                refreshMode = False
            # print(linedata)
            check_line(linedata)
            lastRead += 1
        logObj.close()


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


def get_lastest_result_file(path):
    dirs = os.listdir(path)
    fileDict = {}
    for filename in dirs:
        if "RACE" in filename:
            fullPath = os.path.join(path, filename)
            mtime = int(os.stat(fullPath).st_mtime)
            fileDict[mtime] = fullPath
    key = sorted(fileDict.keys())[-1]
    if int(time.time()) - key > 10:
        print("成绩文件 %s 太老，不予上传" % str(fileDict[key]))
        return False
    else:
        return fileDict[key]


def check_line(linedata):
    global playersDict, lastRead, gInfo, s
    if linedata.find("Car.onSplitCompleted") > -1:
        print("\nlinedata:%s" % linedata)
        data = linedata.split(" ")
        carId = int(data[1])
        gInfo = "ID:" + str(carId) + " sector finished"
        splitTimeCount = int(data[2])
        splitTime = int(data[3])/1000
        if carId in playersDict:
            player = playersDict[carId]
            if splitTimeCount == 0:
                player.mCurSector1 = splitTime
                player.mCurSector2 = NOTIME
                player.mCurSector3 = NOTIME
            elif splitTimeCount == 1:
                player.mCurSector2 = splitTime
                player.mCurSector3 = NOTIME
            elif splitTimeCount == 2:
                player.mCurSector3 = splitTime
            playersDict[carId] = player

        else:
            print("CarId:%s is not ready yet,try to get carInfo" % carId)
            gInfo = "ID:" + str(carId) + " unknow,requiring"
            s.getCarInfo(carId)
            s.processServerPackets(1)


def getJson():
    global gInfo, sessionInfo
    print("\r%s 等待数据。。。。。。" % get_time_str(), end="")
    playersDictForJson = {}
    current_time = int(time.time())
    if current_time % 15 == 0:
        getSessionInfo()
    for carId in playersDict:
        playersDictForJson[carId] = playersDict[carId].__dict__
    if not playersDictForJson:
        gInfo = time.strftime("%H:%M:%S", time.localtime())

    data = {"mInfo": gInfo, "mVehicles": playersDictForJson, "sessionInfo": sessionInfo.__dict__}  # gInfo = global info
    try:
        jsonStr = json.dumps(data, ensure_ascii=False)
        return jsonStr
    except Exception:
        traceback.print_exc()
        input()
        sys.exit(0)


def get_ac_cfg(cfg):
    config = configparser.ConfigParser()
    try:
        config.read(cfg)
        return config['SERVER']
    except Exception:
        traceback.print_exc()
        input()
        sys.exit(0)


def get_carInfo():
    global s, gInfo
    for i in range(maxPlayer):
        gInfo = "Getting ID:%s" % i
        print("\r获取 car info %s,稍等..." % i, end="")
        s.getCarInfo(i)
        s.processServerPackets(1)
    gInfo = "等待车辆信息"


def get_time_str():
    return time.strftime(">%m-%d %H:%M:%S ", time.localtime())


def do_post(data, url):
    print("\n%s 发送数据：%s" % (get_time_str(), data))
    data = {"data": data}
    try:
        re = requests.post(url=url, data=data, headers=headers)
        print("%s 服务器返回：" % get_time_str())
        re_content = str(re.content.decode('utf-8'))
        print(re_content)
        return True
    except WindowsError:
        traceback.print_exc()
        print("%s post超时，下次post再发送本次数据" % get_time_str())
        return False


def gen_onlineList():
    global online_log
    print("生成在线名单")
    playerCount = 0
    guidList = ""
    for carId in playersDict:
        player = playersDict[carId]
        if player.isConnected is True:
            playerCount = playerCount + 1
            guidList = "%s|%s" % (guidList, player.guid)
    new_online_log = "%s,%s" % (playerCount, guidList)
    if new_online_log != online_log:
        post_url = "https://www.srfcworld.com/misc/server_status?sn=%s&DEBUG=1" % ini['sid']
        do_post(new_online_log, post_url)
        online_log = new_online_log
    return playerCount


def getSessionInfo():
    global s
    s.getSessionInfo()  # elapsedMS  sessionType = 1 for practice  sessionTime = 120 (min)
    s.processServerPackets(1)
    print("\r%s 获取Session信息" % get_time_str(), end="")


def main_udp_watcher(s):
    while True:
        s.processServerPackets()


def main():
    global s
    s = ACServerPlugin(rcvPort, sendPort, callback)
    s.enableRealtimeReport(100)
    s.processServerPackets(0)
    getSessionInfo()
    # gen_onlineList()
    
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
    print("SRFC AC SERVER UDP TRACKER 0.9\n\n")
    s = ""  # ac server obj
    gInfo = "实时服务器已经开启,版本0.9"  # 全局信息传输，传输get car info等信息
    iniObj = IniHandle()
    ini = iniObj.read()
    udp_watchers = 0  # 记录观看者数量
    ACPath = ini['AC_path']
    logPath = ACPath + "logs/session/"
    resultPath = ACPath + "results/"
    ac_cfg = get_ac_cfg(ACPath + "cfg/server_cfg.ini")
    print("Server:" + ac_cfg['NAME'])
    maxPlayer = int(ac_cfg['MAX_CLIENTS'])
    print("Max player:" + str(maxPlayer))
    online_log = ""
    latestResultFile = ''
    sessionInfo = ''
    rcvPort = int(ini['UDP_PLUGIN_ADDRESS'])
    sendPort = int(ini['UDP_PLUGIN_LOCAL_PORT'])
    if ini['Output_split_time'] == "1":
        print("计时段记录功能开启")
        logFile = get_lastest_file(logPath)
        logObj = ServerLogHandle(logFile)
        lastlogLineCount = logObj.countLines() - 1
        lastRead = lastlogLineCount  # 若重启，直接从最后行开始
        print(logFile)
        print("Log 行数:" + str(lastlogLineCount))
        print("上次读到:" + str(lastRead))

    if ini['daily'] == "1":
        print("日赛记录功能开启")

    try:
        main()
    except Exception as e:
        errorHandle("main error！")
