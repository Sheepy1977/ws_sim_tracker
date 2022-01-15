#!/usr/bin/env python
# import os
import requests
import sys
import json
from broadcast import broadcast
import threading
from acplugins4python.ac_server_protocol import *
from acplugins4python.ac_server_plugin import *
from lib.mylib import *
import sqlite3

playersDict = {}
NOTIME = 0
headers = {'user-agent': 'SRFC AC TRACKER/1.0'}


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


class Db:  # 2021.7.22 和基于stracker的tracker合并
    def __init__(self, db_file):
        try:
            self.conn = sqlite3.connect(db_file)
            self.cursor = self.conn.cursor()
        except Exception as e:
            errorhandle(e)

    def getsql(self, sql, array_mode=False, fetchall=False):
        self.cursor.execute(sql)
        self.conn.commit()
        if "select" in sql:
            if fetchall is False:
                result = self.cursor.fetchone()
            else:
                result = self.cursor.fetchall()
                return result
            if array_mode is False:
                return result[0]
            else:
                return result


class CheckDB:
    def __init__(self, db):
        self.db = db

    def check(self):
        max_session_id = self.db.getsql("select max(SessionId) from Session")
        re = self.db.getsql("select PlayerInSessionId from PlayerInSession ,Players where SessionID=%d and \
                       Players.PlayerID=PlayerInSession.PlayerID \
                       and Players.IsOnline is not null" % max_session_id, fetchall=True)
        post_data = ""
        for row in re:
            print("PlayerInSessionId:%s" % row[0])
            rowin = self.db.getsql('select LapId ,LapCount from Lap where PlayerInSessionId=%s \
                         and Cuts=0 and (TimeInPitLane=0 or TimeInPitLane is null) \
                         order by LapId desc limit 0,1' % row[0], array_mode=True)
            if rowin is not None:
                lap_id = rowin[0]
                lap_count = rowin[1]
                if lap_id != 0:
                    sql = "select LapTime,SectorTime0,SectorTime1,Name,Car,Timestamp,SteamGuid \
                                 from LapTimes where LapId=%s" % lap_id
                    row3 = self.db.getsql(sql, array_mode=True)
                    lap_time = row3[0] / 1000
                    s0 = row3[1] / 1000
                    s1 = row3[2] / 1000
                    player_name = row3[3]
                    car = row3[4]
                    timestamp = row3[5]
                    steam_guid = row3[6]
                    data = "%s,1,%s,%s,%s,5,6,7,8,%s,%f,%f,%f,%f,%f,%f,%d\n" \
                           % (lap_id, steam_guid, car, player_name, lap_count, s0, s1, lap_time, s0, s1, lap_time, timestamp)
                    post_data = "%s%s" % (post_data, data)
        return post_data


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
    global gInfo
    gInfo = "New SESSION"
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
    else:
        gInfo = "ID:" + str(carId) + " unknow,requiring"
        print("CarId:%s is not ready yet,try to get carInfo" % carId)
        s.getCarInfo(carId)
        s.processServerPackets(1)
        # handle_lap_completed(event)  # 2021.1.22尝试修复部分不记录的情况


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


def getJson():
    global gInfo, sessionInfo

    print("\r%s 等待数据。。。。。。" % get_time_str(), end="")
    playersDictForJson = {}
    current_time = int(time.time())
    # if current_time % 3 == 0:
    #    checkStrackerDb()
    if current_time % 15 == 0:
        getSessionInfo()
        checkStrackerDb()
    for carId in playersDict:
        playersDictForJson[carId] = playersDict[carId].__dict__
    if not playersDictForJson:
        gInfo = time.strftime("%H:%M:%S", time.localtime())

    data = {"mInfo": gInfo, "mVehicles": playersDictForJson}  # gInfo = global info
    try:
        jsonStr = json.dumps(data, ensure_ascii=False)
        return jsonStr
    except Exception:
        traceback.print_exc()
        input()
        sys.exit(0)


def checkStrackerDb():
    db = Db(ini['db'])  # sqlite 对象只能在当前线程内使用，所以要在这里创建
    global playersDict, old_post_data
    playerCount = 0
    for carId in playersDict:
        player = playersDict[carId]
        if player.isConnected is True:
            playerCount = playerCount + 1
    if playerCount > 0:
        try:
            new_post_data = CheckDB(db).check()
            if new_post_data != "" and new_post_data != old_post_data:
                post_url = "https://www.srfcworld.com/misc/do_log?sn=%s&DEBUG=1" % ini['sid']
                re = do_post(new_post_data, post_url)
                if re is True:
                    old_post_data = new_post_data
        except Exception:
            traceback.print_exc()
            input()
            sys.exit(0)

    post_url = "https://www.srfcworld.com/misc/server_status?sn=%s&DEBUG=1" % ini['sid']
    do_post(online_log, post_url)  # 定期ping服务器，避免n/a显示


def get_carInfo():
    global s, gInfo
    for i in range(30):
        gInfo = "Getting ID:%s" % i
        print("\r获取 car info %s,稍等..." % i, end="")
        s.getCarInfo(i)
        s.processServerPackets(1)
    gInfo = "等待车辆信息"


def try_get_carInfo(i):
    global car_info_timer
    car_info_remain_time = car_info_timer[i]
    if car_info_remain_time <= 0:
        print("\r获取 car info %s,稍等..." % i, end="")
        car_info_timer[i] = 100 #此处设定了一个100的倒计时值。避免多次重复获取
        s.getCarInfo(i)
        s.processServerPackets(1)
    else:
        car_info_timer[i] = car_info_timer[i] - 1
    car_info_timer[i] = car_info_timer[i] - 1


def get_time_str():
    return time.strftime(">%m-%d %H:%M:%S ", time.localtime())


def do_post(data, url):
    print("\n%s 发送数据：%s" % (get_time_str(), data))
    data = {"data": data}
    try:
        re = requests.post(url=url, data=data, headers=headers, timeout=10)
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

    playerCount = 0
    guidList = ""
    for carId in playersDict:
        player = playersDict[carId]
        if player.isConnected is True:
            playerCount = playerCount + 1
            guidList = "%s|%s" % (guidList, player.guid)
    new_online_log = "%s,%s" % (playerCount, guidList)
    if new_online_log != online_log:
        print("生成在线名单")
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
    # 通过启动两个线程来实现wss实时传送车辆数据。
    # t1线程为wss主广播线程，通过getJson函数将playerDict字典（其中存储了所有服务器内玩家实时数据）转换成json，通过wss广播出去。
    # 在getJson中每3秒访问一次stracker 数据库，将玩家成绩上传srfc（因原直接udp读取lap_complete模式有bug，丢数据严重，懒得查了，直接用stracker)
    # t2线程则是启动对ac udp的监听，通过监听不同的event，再调用不同的函数来更新playerDict字典

    global s
    s = ACServerPlugin(rcvPort, sendPort, callback)
    s.enableRealtimeReport(100)
    s.processServerPackets(0)
    getSessionInfo()
    # gen_onlineList()

    global car_info_timer
    car_info_timer = {} # 加入这个计时器以便避免反复连续多次请求car info的情况

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
    print("SRFC AC SERVER UDP TRACKER 1.00\nBase Stracker version\n")
    s = ""  # ac server obj
    gInfo = "实时服务器已经开启,版本1.01"  # 全局信息传输，传输get car info等信息
    iniObj = IniHandle()
    ini = iniObj.read()
    udp_watchers = 0  # 记录观看者数量
    old_post_data = ""

    online_log = ""
    sessionInfo = ''
    rcvPort = int(ini['UDP_PLUGIN_ADDRESS'])
    sendPort = int(ini['UDP_PLUGIN_LOCAL_PORT'])

    try:
        main()
    except Exception as e:
        errorHandle("main error！")
