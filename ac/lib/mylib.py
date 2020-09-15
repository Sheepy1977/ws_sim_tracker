import configparser
import linecache
import traceback
import smtplib
from email.mime.text import MIMEText
from email.utils import formataddr


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


class IniHandle:
    def __init__(self, configFile="config.ini"):
        self.config = configparser.ConfigParser()
        try:
            self.config.read(configFile)
        except Exception as e:
            errorHandle(e)

    def read(self):
        try:
            return self.config['config']
        except Exception as e:
            errorHandle("config文件不存在或者格式错误！")

    def set(self, key, value):
        try:
            self.config.set("config", key, value)
        except Exception as e:
            errorHandle("config文件不存在或者格式错误！")


def errorHandle(msg):
    detail = traceback.format_exc()
    errmsg = "Error:%s\n%s" % (msg, detail)
    print(errmsg)

    if "debug" in ini.keys():
        if ini['debug'] == '1':
            send_err_mail(errmsg)
    input("出错了，确认错误信息后按回车键关闭本窗口")
    sys.exit(0)


def send_err_mail(msg):
    sid = ini['sid']
    my_sender = "srfc@vip.qq.com"
    my_pass = "iyidzyxjvqhscbae"
    my_user = "srfc@vip.qq.com"
    try:
        msg = MIMEText("SID:%s\n%s " % (sid, msg), 'plain', 'utf-8')
        msg['From'] = formataddr(("AC_ws_tracker", my_sender))
        msg['To'] = formataddr(("SRFC", my_user))
        msg['Subject'] = "AC WS监控出错"
        server = smtplib.SMTP_SSL("smtp.qq.com", 465)
        server.login(my_sender, my_pass)
        server.sendmail(my_sender, [my_user, ], msg.as_string())
        server.quit()
        print("通知邮件已经发送给管理员")
    except Exception:
        print("通知邮件发送失败")
        traceback.print_exc()
        sys.exit(0)
