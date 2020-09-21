"""SRFC RF2 SERVER TRACKER by Sheepy 2020"""

import sys
import requests
import json
import time
import logging
import configparser
import traceback
import smtplib
import asyncio
from email.mime.text import MIMEText
from email.utils import formataddr
from wss_broadcast import wss_broadcast
import threading

headers = {'user-agent': 'SRFC rF2 TRACK/0.6'}


class IniHandle:
    def __init__(self):
        self.config = configparser.ConfigParser()
        try:
            self.config.read("config.ini")
        except Exception as e:
            errorHandle(e)

    def read(self):
        try:
            return self.config['config']
        except Exception as e:
            errorHandle("config文件不存在或者格式错误！")


class GetData:
    def __init__(self):
        self.url = "http://127.0.0.1:34297/getScoringInfo"
        self.r = requests.get(self.url)
        self.jsonData = json.loads(self.r.text)

    def decode(self):
        row = self.jsonData
        if "mTrackName" in row.keys():
            track = row['mTrackName']
            airTemp = round(float(row['mAmbientTemp']), 2)
            trackTemp = round(float(row['mTrackTemp']), 2)
            trackWet = round(float(row['mAvgPathWetness']), 2) * 100
            guests = int(row['mNumVehicles'])
            session = row['mSession']
            post_data = ""
            onlineList = ""
            if guests > 0:
                for row2 in row['mVehicles']:
                    playerName = row2['mDriverName']
                    carName = "%s-%s" % (row2['mVehicleName'], row2['mVehicleClass'])
                    carName = carName.replace(",", ".")
                    laps = row2['mTotalLaps']
                    last1 = row2['mLastSector1']
                    last2 = row2['mLastSector2']
                    lastlap = row2['mLastLapTime']
                    if lastlap > 0:
                        coord = {'playerName': playerName, 'carName': carName, 'laps': laps, 'last1': last1, 'last2': last2,
                                 'lastlap': lastlap, 'session': session, 'airTemp': airTemp, 'trackTemp': trackTemp,
                                 'trackWet': trackWet,
                                 'pit': 0}
                        data = """rf2,1,{playerName},{carName},4,5,6,7,{pit},{laps},{last1},{last2},{lastlap},{last1},{last2},{lastlap},16,{session},{airTemp},{trackTemp},{trackWet}\n""".format(**coord)
                        post_data = "%s%s" % (post_data, data)
                    onlineList = "%s|%s" % (onlineList, playerName)
            onlineList = "%d,%s" % (guests, onlineList)
            return [post_data, onlineList, track]
        else:
            return None


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


def dolog(logData, logName):
    logging.basicConfig(filename=logName, filemode="w", level=logging.INFO,
                        format='%(asctime)s - %(pathname)s[line:%(lineno)d]: %(message)s)')
    logging.info(logData)


def getTimeStr():
    return time.strftime(">%m-%d %H:%M:%S ", time.localtime())


def errorHandle(msg):
    detail = traceback.format_exc()
    errmsg = "Error:%s\n%s" % (msg, detail)
    print(errmsg)
    ini = IniHandle().read()
    if "debug" in ini.keys():
        if ini['debug'] == '1':
            send_err_mail(errmsg)
    input("出错了，确认错误信息后按回车键关闭本窗口")
    sys.exit(0)


def send_err_mail(msg):
    ini = IniHandle().read()
    sid = ini['sid']
    my_sender = "srfc@vip.qq.com"
    my_pass = "ofrdbwviisprcbdj"
    my_user = "srfc@vip.qq.com"
    try:
        msg = MIMEText("SID:%s\n%s " % (sid, msg), 'plain', 'utf-8')
        msg['From'] = formataddr(("ACCStracker", my_sender))
        msg['To'] = formataddr(("SRFC", my_user))
        msg['Subject'] = "rF2监控出错"
        server = smtplib.SMTP_SSL("smtp.qq.com", 465)
        server.login(my_sender, my_pass)
        server.sendmail(my_sender, [my_user, ], msg.as_string())
        server.quit()
        print("通知邮件已经发送给管理员")
    except Exception:
        print("通知邮件发送失败")
        traceback.print_exc()
        sys.exit(0)


def get_rf2_ws_data():
    t = requests.get("http://127.0.0.1:34297/getScoringInfo").text
    data = t.replace("\t", "").replace("\n", "").replace("\\", "")
    re = json.dumps(data, ensure_ascii=False)
    return re


class Player:
    def __init__(self, driverName="", uid=0, cname=""):
        self.mDriverName = driverName  # 玩家在游戏里的名字
        self.uid = uid
        self.cname = cname


def refresh(config):
    sid = config['sid']
    count = 0
    msg = "."
    inter = int(config['interval'])
    old_onlineList = ""
    old_postData = ""
    while True:
        if count == 0:
            re = GetData().decode()
            if re is not None:
                postData = re[0]
                onlineList = re[1]
                track = re[2]
                if postData != old_postData and postData != "":
                    post_url = "https://www.srfcworld.com/misc/do_log?sn=%s&DEBUG=1" % sid
                    doPost(postData, post_url)
                    old_postData = postData
                if onlineList != old_onlineList:
                    post_url = "https://www.srfcworld.com/misc/server_status?sn=%s&DEBUG=1" % sid
                    doPost(onlineList, post_url)
                    old_onlineList = onlineList
                    print("\n%s%s 在线名单:%s" % (getTimeStr(), track, onlineList))
        print("\r%s %s/%s扫描中%s  " % (getTimeStr(), count, inter, msg), end="")
        count += 1
        msg += "."
        if count > inter:
            count = 0
        if msg == "....":
            msg = "."
        time.sleep(1)


def main():
    print("SRFC rF2 Server TRACKER v0.0.41 by Sheepy\n")
    sys.stderr = open("err.log", "w")
    config = IniHandle().read()
    check = wss_broadcast.checkConfig(config)

    if check is not False:
        sslDebug = check[1]
        wss_inter = check[2]
        print("Wss interval set to " + str(wss_inter) + "sec")
        t1 = threading.Thread(target=wss_broadcast.wss_broadcast,
                              args=(config['wss_port'], config['sslKey'], config['sslCert'], sslDebug, get_rf2_ws_data, wss_inter))
        # 第5个参数是具体获得数据的函数名，比如get_ac_ws_data
        t2 = threading.Thread(target=refresh, args=(config,))
        try:
            t1.start()
            t2.start()
        except Exception as e:
            print("error on thread")
            errorHandle(e)
    else:
        print("\nNo SSL config found,websockets service disabled.")
        try:
            refresh(config)
        except Exception as e:
            errorHandle(e)


playersList = {}

if __name__ == "__main__":
    try:
        main()
    except Exception as e:
        errorHandle(e)
