"""SRFC ACC TRACKER by SHEEPY 2020"""
import codecs
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

headers = {'user-agent': 'SRFC ACC TRACK/0.351'}
debug = False
'''
[config]
acc_log=C:/Program Files (x86)/acc/server/log/server.log
online_log=C:/Program Files (x86)/AC/stracker/acc_server_status.log
post_url=https://www.srfcworld.com/misc/do_log?sn=acc&DEBUG=1

'''
startTime = round(time.time())
conditionDict = {"setTrack": "Track",
                 "newJoin": "New connection request",
                 "newId": "Creating new car connection",
                 "reConnect": "Recognized reconnect",
                 "newLap": "Lap carId",
                 "disconnect": "has no driving connection"}


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


class DbHandle:
    def __init__(self):
        try:
            self.db = sqlite3.connect("acc_sqlite3.db3")
            self.cursor = self.db.cursor()  # 连接数据库
        except Exception as error:
            errorHandle(error)
        try:
            self.getsql("select * from acc_lastread", row_mode=True)
        except sqlite3.OperationalError:
            sql = "CREATE TABLE 'acc_lastread' ('id' tinyint(4) ,'lastRead' int(20) ," \
                  "'startTime' int(20) ,'track' varchar(255) ,PRIMARY KEY ('id'));"
            self.getsql(sql)
            sql = "CREATE TABLE 'acc_server_online' (" \
                  "'id' integer PRIMARY KEY autoincrement," \
                  "  'guid' varchar(20) DEFAULT NULL," \
                  "  'carId' varchar(4) DEFAULT NULL," \
                  "  'carModel' varchar(4) DEFAULT NULL," \
                  "  'playerId' varchar(20) DEFAULT NULL," \
                  "  'continueLap' smallint(6) DEFAULT '0')"
            self.getsql(sql)
            sql = "insert into acc_lastread (lastRead,startTime,id) values (0,0,1)"
            self.getsql(sql)

    def dbInit(self):
        self.getsql("update acc_lastread set lastRead = 0,startTime = %d where id = 1" % startTime)
        self.getsql("DELETE FROM 'acc_server_online'")
        self.getsql("DELETE FROM sqlite_sequence WHERE name = 'acc_server_online'")

    def getsql(self, sql, row_mode=False, fetchall=False):
        self.cursor.execute(sql)
        self.db.commit()
        if "select" in sql:
            if fetchall is False:
                result = self.cursor.fetchone()
            else:
                result = self.cursor.fetchall()
            if row_mode is False:
                return result[0]
            else:
                return result


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

    def __init__(self, data, config, db, cardict):
        if data is None:
            print("Error!")
            sys.exit(0)
        self.data = data
        self.config = config
        self.db = db
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
        self.db.getsql("update acc_lastread set track = '%s' where id = 1" % track)

    def newJoin(self):
        arr = self.data.split()
        length = len(arr)
        guid = arr[(length - 5)]  # 120264: New connection request: id 0 baifa JJJ S76561198071914505 on car model 2
        guid = guid[1:]
        playerId = arr[(length - 7)]
        print("\n%s %s 玩家加入，GUID：%s ,%s" % (getTimeStr(), self.getLineId(), guid, playerId), end='')
        self.db.getsql("delete from acc_server_online where guid = %s" % guid)
        self.db.getsql("insert into acc_server_online (guid, playerId) values ('%s','%s')" % (guid, playerId))

    def reConnect(self):
        print("，重联，carId：", end='')
        self.assignId()

    def newId(self):
        print("，carId：", end='')
        self.assignId()

    def assignId(self):
        arr = self.data.split()
        index = arr.index("carId") + 1
        carId = arr[index].strip()[:-1]
        index = arr.index("carModel") + 1
        carModelId = arr[index].strip()[:-1]
        carModelName = self.carDict[carModelId]
        print(carId, end='')
        print("，车型：%s" % carModelName)
        lastId = self.db.getsql("select id from acc_server_online where carId is NULL order by id desc limit 0,1")
        sql = "update acc_server_online set carId = %s,carModel = '%s' where id = %s" % (carId, carModelId, lastId)
        self.db.getsql(sql)
        if debug is True:
            print(sql)
        self.genOnlineList()
        return sql

    def newLap(self):
        # Lap carId 1002, driverId 0, lapTime 2:02:814, timestampMS 18211981.000000, flags: %d0, S1 0:39:237,
        # S2 0:43:122, S3 0:40:455, fuel 55.000000
        dolog(self.data, "livelog.log")
        arr = self.data.split()
        if "S2" not in arr:
            return
        carId = arr[arr.index("carId") + 1].strip()[:-1]
        print("\n%s %s 新的圈速，CARID：%s" % (getTimeStr(), self.getLineId(), carId), end='')
        s1str = arr[arr.index("S1") + 1].strip()[:-1]
        s1 = str2ms(s1str)
        s2str = arr[arr.index("S2") + 1].strip()[:-1]
        s2 = str2ms(s2str)
        lapTimeStr = arr[arr.index("lapTime") + 1].strip()[:-1]
        lapTime = str2ms(lapTimeStr)
        timestamp = int(arr[arr.index("timestampMS") + 1].strip()[:-8]) + startTime
        if lapTimeStr == '35791:23:647' or s1 <= 0 or s2 <= 0:
            print("，无需处理")
            return
        if "hasCut" in self.data or "OutLap" in self.data or lapTime <= 0:
            self.db.getsql("update acc_server_online set continueLap = 0 where carId = %s" % carId)
            print("，非法圈")
            return
        else:
            self.db.getsql("update  acc_server_online set continueLap = continueLap + 1 where carId = %s" % carId)
            print("，合法圈 %s %s %s" % (s1str, s2str, lapTimeStr))
            temp = self.db.getsql("select guid,carModel,continueLap,playerId from acc_server_online where carId = %s" % carId,
                                  True)
            if temp is not None:
                guid = temp[0]
                carModel = temp[1]
                continueLap = temp[2]
                playerId = temp[3]
                carName = self.carDict[carModel]
                data = "0,1,%s,%s,%s,5,6,7,8,%s,%f,%f,%f,%f,%f,%f,%d\n" % (
                    guid, carName, playerId, continueLap, s1, s2, lapTime, s1, s2, lapTime, timestamp)
                return data

    def getLineId(self):
        arr = self.data.split(":")
        return "(%s)" % arr[0].strip()

    def disconnect(self):
        arr = self.data.split()
        index = arr.index("car") + 1
        carId = arr[index].strip()
        print("\n%s %s 玩家退出，CARID：%s" % (getTimeStr(), self.getLineId(), carId))
        sql = "delete from acc_server_online where carId = %s" % carId
        self.db.getsql(sql)
        self.genOnlineList()

    def genOnlineList(self):
        sql = "select * from acc_server_online where carId > 1000"
        ok = self.db.getsql(sql, "all", "all")
        guidList = ""
        count = 0
        for row in ok:
            guid = row[1]
            guidList = "%s|%s" % (guidList, guid)
            count += 1
        onlineList = "%d,%s" % (count, guidList[:-1])
        onlineLog = open("online.log", "a")
        onlineListData = "%s %s\n" % (getTimeStr(), onlineList)
        onlineLog.write(onlineListData)
        onlineLog.close()
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


def getTimeStr():
    return time.strftime(">%m-%d %H:%M:%S ", time.localtime())


def dolog(logData, logName):
    logging.basicConfig(filename=logName, filemode="w", level=logging.INFO,
                        format='%(asctime)s - %(pathname)s[line:%(lineno)d]: %(message)s)')
    logging.info(logData)


def doPost(data, url):
    dolog(data, "postlog.log")
    print("\n%s 发送数据：%s" % (getTimeStr(), data))
    data = {"data": data}
    try:
        re = requests.post(url=url, data=data, headers=headers)
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
    sendMail(error)
    input("出错了，确认错误信息后按回车键关闭本窗口")
    sys.exit(0)


def sendMail(error):
    ini = IniHandle('config.ini')
    if ini.debug() == '1':
        sid = ini.readConfig()['sid']
        my_sender = "srfc@vip.qq.com"
        my_pass = "ofrdbwviisprcbdj"
        my_user = "srfc@vip.qq.com"
        try:
            msg = MIMEText("SID:%s\n%s " % (sid, error), 'plain', 'utf-8')
            msg['From'] = formataddr(("ACCStracker", my_sender))
            msg['To'] = formataddr(("SRFC", my_user))
            msg['Subject'] = "ACC监控出错"
            server = smtplib.SMTP_SSL("smtp.qq.com", 465)
            server.login(my_sender, my_pass)
            server.sendmail(my_sender, [my_user, ], msg.as_string())
            server.quit()
            print("通知邮件已经发送给管理员")
        except Exception:
            print("通知邮件发送失败")
            traceback.print_exc()
            sys.exit(0)
    else:
        print()


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
    print("SRFC ACC Server logger ver 0.351 by Sheepy")
    # init#
    ini = IniHandle("config.ini")
    config = ini.readConfig()
    db = DbHandle()
    carDict = ini.readCars()
    postData = ""
    refreshMode = False
    msg = "."
    while True:
        convert(config['acc_log'])  # 转换文件编码
        log = ServerLogHandle("C:/decode_log.log")
        logLineCount = log.countLines() - 1  # log行总数
        readLineNo = db.getsql("select lastRead from acc_lastread")
        if readLineNo > logLineCount:
            print("检测到ACC服重启，监控数据库重置")
            print()
            print("\n>0人在线")
            sid = config['sid']
            post_url = "https://www.srfcworld.com/misc/server_status?sn=%s&DEBUG=1" % sid
            doPost("0,", post_url)
            db.dbInit()  # 清理数据库

        elif readLineNo < logLineCount:
            print("\r%s %d/%d 已读取，扫描server.log中 %s   " % (getTimeStr(), readLineNo, logLineCount, msg), end="")
            lineData = log.getLine(readLineNo, refreshMode)
            refreshMode = False
            data = DataHandle(lineData, config, db, carDict)
            re = data.checkData()
            db.getsql("update acc_lastread set lastRead = lastRead + 1 where id=1")
            if re is not None:
                postData = "%s%s" % (re, postData)
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


if __name__ == '__main__':
    try:
        main()
    except Exception as e:
        errorHandle(e)
