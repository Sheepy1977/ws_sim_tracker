"""SRFC ACC TRACKER by SHEEPY 2022"""
import codecs
import os
import sys
import sqlite3
import requests  # 非标准库
import time
import linecache
import logging
import configparser
import traceback
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr

headers = {'user-agent': 'SRFC ACC TRACK/0.47'}
debug = False
'''
[config]
acc_log=C:/Program Files (x86)/acc/server/log/server.log
post_url=https://www.srfcworld.com/misc/do_log?sn=acc&DEBUG=1

'''
startTime = round(time.time())
conditionDict = {"setTrack": "Track",
                 "newJoin": "New connection request",
                 "newId": "Creating new car connection",
                 "reConnect": "Recognized reconnect",
                 "newLap": "Lap carId",
                 "disconnect": "has no driving connection"}

playersDict = {}
currentGuid = ""  # 最近的一次guid，根据newJoin得来


class Player:
    def __init__(self, guid="", carId="", carModel="", playerId="", continuedLap=0):
        self.guid = guid
        self.carId = carId
        self.carModel = carModel
        self.playerId = playerId  # playerid = plyname
        self.continuedLap = continuedLap


class IniHandle:
    def __init__(self, inifile):
        self.config = configparser.ConfigParser()
        try:
            self.config.read(inifile)
        except Exception as e:
            errorHandle(e)

    def readConfig(self):
        try:
            return self.config['config']
        except Exception as e:
            errorHandle("config文件不存在或者格式错误！")

    def readCars(self):
        try:
            return dict(self.config['cars'])
        except Exception as e:
            errorHandle("config文件不存在或者格式错误！")

    def debug(self):
        try:
            return self.config['debug']['debug']
        except Exception as e:
            errorHandle("config文件不存在或者格式错误！")


class ServerLogHandle:
    """server log操作类"""

    def __init__(self, filename):
        self.file = open(filename, "rb")
        self.fileName = filename

    def countLines(self):
        count = -1
        thefile = self.file
        for count, line in enumerate(thefile):
            pass
            count += 1
        return count

    def getLine(self, lineno, mode=False):
        if mode is True:
            linecache.updatecache(self.fileName)
        return linecache.getline(self.fileName, lineno).strip()  # 去除首尾空格

    def close(self):
        self.file.close()


class DataHandle:
    """处理单行数据"""

    def __init__(self, data, config, cardict):
        if data is None:
            print("Error!")
            sys.exit(0)
        self.data = data
        self.config = config
        self.carDict = cardict

    def checkData(self):
        # print("line:%s" % self.getLineId())
        for key in conditionDict:
            val = conditionDict[key]
            if self.data.find(val) > -1:
                if debug is True:
                    print(key + "->>>" + self.data)
                re = eval("self.%s" % key)()  # 直接用变量名作为函数名
                return re

    def setTrack(self):
        arr = self.data.split()
        track = arr[2]
        print("%s 赛道设置为：%s" % (getTimeStr(), track))
        # self.db.getsql("update acc_lastread set track = '%s' where id = 1" % track)

    def newJoin(self):
        global playersDict, currentGuid
        arr = self.data.split()
        length = len(arr)
        guid = arr[(length - 5)]  # 120264: New connection request: id 0 baifa JJJ S76561198071914505 on car model 2
        guid = guid[1:]
        playerId = arr[(length - 7)].replace("'", "")
        print("\n%s %s 玩家加入，GUID：%s ,%s" % (getTimeStr(), self.getLineId(), guid, playerId), end='')
        if guid not in playersDict.keys():
            player = Player(guid=guid)
        else:
            player = playersDict[guid]
        player.playerId = playerId
        playersDict[guid] = player
        currentGuid = guid

    def reConnect(self):
        print("，重联，carId：", end='')
        self.assignCarId()

    def newId(self):
        print("，carId：", end='')
        self.assignCarId()

    def assignCarId(self):
        arr = self.data.split()
        index = arr.index("carId") + 1
        carId = arr[index].strip()[:-1]
        index = arr.index("carModel") + 1
        carModelId = arr[index].strip()[:-1]
        carModel = self.carDict[carModelId]
        print(carId, end='')
        print("，车型：%s" % carModel)
        if currentGuid in playersDict.keys():
            player = playersDict[currentGuid]
            player.carId = carId
            player.carModel = carModel
            playersDict[currentGuid] = player
            self.genOnlineList()
        else:
            print("\nassignCarId出错，找不到对应的guid")

    def newLap(self):
        global playersDict
        # Lap carId 1002, driverId 0, lapTime 2:02:814, timestampMS 18211981.000000, flags: %d0, S1 0:39:237,
        # S2 0:43:122, S3 0:40:455, fuel 55.000000
        #  dolog(self.data, "livelog.log")
        arr = self.data.split()
        if "S2" not in arr:
            return
        carId = arr[arr.index("carId") + 1].strip()[:-1]
        print("\n%s %s 新的圈速，CARID：%s" % (getTimeStr(), self.getLineId(), carId), end='')
        guid = get_playerGuid(carId)
        if guid == 'n/a':
            print("\n找不到对应的guid")
            return
        s1str = arr[arr.index("S1") + 1].strip()[:-1]
        s1 = str2ms(s1str)
        s2str = arr[arr.index("S2") + 1].strip()[:-1]
        s2 = str2ms(s2str)
        lapTimeStr = arr[arr.index("lapTime") + 1].strip()[:-1]
        lapTime = str2ms(lapTimeStr)
        # timestamp = int(arr[arr.index("timestampMS") + 1].strip()[:-10]) + startTime
        timestamp = round(time.time())
        if lapTimeStr == '35791:23:647' or s1 <= 0 or s2 <= 0:
            print("，无需处理")
            return
        if "hasCut" in self.data or "OutLap" in self.data or lapTime <= 0:
            playersDict[guid].continuedLap = 0
            print("，非法圈")
            return
        else:
            playersDict[guid].continuedLap += 1
            print("，合法圈 %s %s %s" % (s1str, s2str, lapTimeStr))

            carModel = playersDict[guid].carModel
            continuedLap = playersDict[guid].continuedLap
            playerId = playersDict[guid].playerId
            data = "0,1,%s,%s,%s,5,6,7,8,%s,%f,%f,%f,%f,%f,%f,%d\n" % (
                guid, carModel, playerId, continuedLap, s1, s2, lapTime, s1, s2, lapTime, timestamp)
            return data

    def getLineId(self):
        arr = self.data.split(":")
        return "(%s)" % arr[0].strip()

    def disconnect(self):
        global playersDict
        arr = self.data.split()
        index = arr.index("car") + 1
        carId = arr[index].strip()
        print("\n%s %s 玩家退出，CARID：%s" % (getTimeStr(), self.getLineId(), carId))
        guid = get_playerGuid(carId)
        if guid in playersDict.keys():
            del playersDict[guid]
        self.genOnlineList()

    def genOnlineList(self):
        global genOnlineListMode
        if genOnlineListMode == 1:
            guidList = ""
            count = 0
            for guid in playersDict.keys():
                guidList = "%s|%s" % (guidList, guid)
                count += 1
            onlineList = "%d,%s" % (count, guidList[:-1])
            # onlineListData = "%s %s\n" % (getTimeStr(), onlineList)
            print("\n>%d人在线，名单：%s" % (count, onlineList))
            sid = self.config['sid']
            post_url = "https://www.srfcworld.com/misc/server_status?sn=%s&DEBUG=1" % sid
            doPost(onlineList, post_url)


def str2ms(strr):
    arr = strr.split(":")
    tmin = int(arr[0].strip())
    tsec = int(arr[1].strip())
    tms = int(arr[2].strip())
    re = float(tmin * 60 + tsec + tms / 1000)
    return re


def get_playerGuid(carId):
    global playersDict
    for key in playersDict.keys():
        if playersDict[key].carId == carId:
            return playersDict[key].guid
    return "n/a"


def getTimeStr():
    return time.strftime("acc 0.47 >>%m-%d %H:%M:%S ", time.localtime())


def dolog(logData, logName):
    logging.basicConfig(filename=logName, filemode="w", level=logging.INFO,
                        format='%(asctime)s - %(pathname)s[line:%(lineno)d]: %(message)s)')
    logging.info(logData)


def doPost(data, url):
    dolog(data, "postlog.log")
    print("\n%s 发送数据：%s" % (getTimeStr(), data))
    data = {"data": data}
    try:
        re = requests.post(url=url, data=data, headers=headers, timeout=10)
        print("%s 服务器返回：" % getTimeStr())
        reContent = str(re.content.decode('utf-8'))
        dolog(reContent, "postlog.log")
        print(reContent)
        return True
    except WindowsError:
        print("%s post超时，下次post再发送本次数据" % getTimeStr())
        return False


def errorHandle(error):
    detail = traceback.format_exc()
    error = "Error:%s\n%s" % (error, detail)
    print(error)
    input("出错了，确认错误信息后按回车键关闭本窗口")
    sys.exit(0)


def convert(file_name, in_code="iso-8859-1", out_code="UTF-8"):
    """
    该程序用于将目录下的文件从指定格式转换到指定格式，默认的是GBK转到UTF-8
    :param file:    文件路径
    :param in_code:  输入文件格式
    :param out_code: 输出文件格式
    :return:
    """
    try:
        with codecs.open(file_name, 'r', in_code) as f_in:
            new_content = f_in.read()
            f_out = codecs.open("C:/decode_log.log", 'w', out_code)
            f_out.write(new_content)
            f_out.close()
    except IOError as err:
        print("I/O error: {0}".format(err))


def main():
    print("SRFC ACC Server tracker ver 0.46 by Sheepy")
    # init#
    ini = IniHandle("config.ini")
    config = ini.readConfig()
    carDict = ini.readCars()
    postData = ""
    refreshMode = False
    msg = "."
    '''
    mtime = int(os.stat(config['acc_log']).st_mtime)
    if int(time.time()) - mtime > 60:
        print("Log文件太老，请重启ACC SERVER之后再启动本tracker")
        input("按回车键退出")
        sys.exit(0)
    '''
    readLineNo = 1
    sleepCount = 0
    global genOnlineListMode
    genOnlineListMode = 1  # 默认发送在线名单有效
    maxPostDataLine = 5
    postDataLineCount = 0  # post出去的data行数计数器，避免过多post造成网络卡死
    convert(config['acc_log'])  # 转换文件编码
    log = ServerLogHandle("C:/decode_log.log")
    logLineCount = log.countLines() - 1  # log行总数
    if logLineCount <= 50:
        post_url = "https://www.srfcworld.com/misc/server_status?sn=%s&DEBUG=1" % config['sid']
        doPost("0,", post_url)

    while True:
        if readLineNo < logLineCount:
            print("\r%s %d/%d 已读取，扫描server.log中 %s   " % (getTimeStr(), readLineNo, logLineCount, msg), end="")
            lineData = log.getLine(readLineNo, refreshMode)
            refreshMode = False
            data = DataHandle(lineData, config, carDict)
            re = data.checkData()
            readLineNo += 1
            if logLineCount - readLineNo > 5000:
                genOnlineListMode = 0  # 大于5000行差距的情况下不生成在线名单，避免回溯log的时候对服务器负担过重
            else:
                genOnlineListMode = 1
            if re is not None:
                postData = "%s%s" % (re, postData)
                postDataLineCount += 1

            if postDataLineCount > maxPostDataLine:
                print("累积发送数据已达%s行，发送" % maxPostDataLine)
                post_url = "https://www.srfcworld.com/misc/do_log?sn=%s&DEBUG=1" % config['sid']
                ok = doPost(postData, post_url)
                if ok:
                    postData = ""  # post成功之后清空
                    postDataLineCount = 0
        else:
            msg += "."
            if msg == '....':
                msg = "."
            print("\r%s %d/%d 已读取，扫描server.log中 %s   " % (getTimeStr(), readLineNo, logLineCount, msg),
                  end="")  # \r代表光标回到本行，结合end，可以实现在控制台持续刷新单行文字
            log.close()  # 关闭读取log
            refreshMode = True
            if postData != "":
                post_url = "https://www.srfcworld.com/misc/do_log?sn=%s&DEBUG=1" % config['sid']
                ok = doPost(postData, post_url)
                if ok:
                    postData = ""  # post成功之后清空
            time.sleep(2)
            convert(config['acc_log'])  # 转换文件编码
            log = ServerLogHandle("C:/decode_log.log")
            logLineCount = log.countLines() - 1  # log行总数
            if sleepCount > 30:
                print("\r%s Ping主数据库。" % getTimeStr())
                sleepCount = 0
                lineData = log.getLine(readLineNo, refreshMode)
                data = DataHandle(lineData, config, carDict)
                data.genOnlineList()
            else:
                sleepCount += 1


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        errorHandle(e)
