import time
import copy
import sys
import os
import socket
import json
import cv
import thread

class TcpClient():
    def __init__(self,ip,port):
        BUFFER_SIZE = 1024
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print "connecting..."
        self.s.connect((ip, port))
        print "done"

    def reconnect(self):
        self.s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        print "reconnecting..."
        self.s.connect((ip, port))
        print "done"

    def tx(self,data):
        data = json.dumps(data)
        #print("sending",data)
        self.s.send(data + "\n")


def writetext(img,textupper=None,textbottom=None):
    padding = 2
    cvfont = cv.InitFont(cv.CV_FONT_HERSHEY_SIMPLEX,1,1)
    textsize,baseline = cv.GetTextSize(textupper,cvfont)
    fontheight = textsize[1]

    fontheight = fontheight + (padding * 2)

    if textupper:
        cv.Rectangle(img,(0,0),(img.width,fontheight),cv.RGB(30,30,50),cv.CV_FILLED)
        cv.PutText(img,textupper,(0,textsize[1] + padding),cvfont,cv.RGB(255,255,255))

    if textbottom:
        cv.Rectangle(img,(0,img.height),(img.width,img.height - fontheight),cv.RGB(30,30,50),cv.CV_FILLED)
        cv.PutText(img,textbottom,(0,img.height - padding),cvfont,cv.RGB(255,255,255))


class Device():
    def __init__(self,source,channel=1):
        self.source = source
        self.channel = channel
        os.system("sudo chmod 777 /dev/video" + str(self.source))
        print("opening video" + str(source) + "...")
        self.capture = cv.CaptureFromCAM(source)
        print("done")

    def changechannel(self,channel):
        os.system("v4l2-ctl -d /dev/video" + str(self.source) + " --set-input=" + str(channel) + "> /dev/null 2> /dev/null")
        time.sleep(0.3)
        self.channel = channel

class Camera():
    def __init__(self,core,device,channel):
        self.core = core
        self.device = device
        self.channel = channel

        self.lasttime = 0

        self.size = None
        self.oldimg = None

    def tickloop(self):
        self.tick()
        start = time.time()
        while ((time.time() - start) < self.core.windowtime):
            self.core.bucket.feed(self.tick())

    def motiondetect(self,img):
        gray = cv.CreateImage(self.size, 8, 1)
        cv.CvtColor(img, gray, cv.CV_BGR2GRAY)

        if not self.oldimg or (time.time() - self.lasttime) > 1:
            self.oldimg = cv.CreateImage(self.size, 8, 1)
            cv.Copy(gray,self.oldimg)
            self.lasttime = time.time()
            return 0

        self.lasttime = time.time()

        diff = cv.CreateImage(self.size, 8, 1)
        cv.AbsDiff(gray,self.oldimg,diff)

        thr = cv.CreateImage(self.size, 8, 1)
        movement = cv.CreateImage(self.size, 8, 1)
        cv.SetZero(movement)

        cv.Threshold(diff,thr,30,1, cv.CV_THRESH_BINARY)
        movecount = cv.CountNonZero(thr)


        color = cv.CreateImage(self.size,8,3)
        cv.Set(color,(255,0,0))

        cv.Copy(color,img,thr)

        cv.Copy(diff,movement,thr)
        cv.ShowImage("movement" + str(self.channel),movement)


        writetext(img,'c' + str(self.channel) + ' a' + str(int(self.core.bucket.value)) + ' m' + str(movecount))

        cv.ShowImage("camera" + str(self.channel), img)

        cv.Copy(gray,self.oldimg)
        self.lasttime = time.time()

        return movecount

    def tick(self):
        if self.device.channel != self.channel:
            self.device.changechannel(self.channel)

        img = cv.QueryFrame(self.device.capture)

        if not self.size:
            self.size = (img.width, img.height)

        motion = self.motiondetect(img)

        cv.WaitKey(10)

        return motion



class AvgBucket():
    def __init__(self):
        self.value = 0
        self.num = 300 # 300 zeros

    def feed(self,value):
        self.num = self.num + 1
        self.value * (1 / self.num)
        chunk = (1.0 / self.num)
        self.value = self.value * chunk * (self.num - 1)
        self.value = self.value + chunk * value

    def __string__(self):
        return str(self.value)

    def __repr__(self):
        return str(self.value)


class videoCore():
    def __init__(self):
        easycap = Device(1)
        self.camera1 = Camera(self,easycap,1)
        self.camera2 = Camera(self,easycap,2)
        self.camera3 = Camera(self,easycap,3)
        self.windowtime = 10
        self.valuesoverride = None
        self.showscore = 1

    def start(self):
        thread.start_new_thread(self.loop, ())

    def loop(self):
        while True:
            self.camera1.tickloop()
            self.camera2.tickloop()
            self.camera3.tickloop()

cap = videoCore()
cap.bucket = AvgBucket()
cap.bucket.team = 'total'
cap.bucket.roundindex = 1
cap.start()

roundindex = 1
teamindex = 0

teams = {}

def switchstate(roundindex,team):
    if not teams.has_key(team):
        print("initialized new team " + team)
        teams[team] = {}
        
    newbucket = AvgBucket()
    newbucket.team = team
    newbucket.roundindex = roundindex
    
    cap.bucket = newbucket # capture to this bucket
    
    teams[team][roundindex] = newbucket
    
    
cap.text1 = "init"
cap.text2 = "init"

def show():
    data = {}

    def translate(name):
        t = { 'elevate': 0, 'illectricity': 1, 'share': 2, 'terraneo': 3, 'total': 4 }
        if not t.has_key(name):
            return 5
        return t[name]

    data['state'] = state = translate(cap.bucket.team)
    data['round'] = roundindex = cap.bucket.roundindex
    data['fail'] = []

    data['text1'] = cap.text1
    data['text2'] = cap.text2
    data['show'] = cap.showscore

    if cap.valuesoverride:
        data['values'] = cap.valuesoverride
        return data

    values = {}

    for teamname in teams:
        if teamname is not 'total':
            if not teams[teamname].has_key(roundindex):
                data['fail'].append(teamname + "-" + str(roundindex))
                val = 0
            else:
                val = teams[teamname][roundindex].value

            values[teamname] = int(val)



    data['values'] = values

    return data


def averagebuckets(buckets):
    total = 0
    for bucket in buckets:
        total = total + bucket.value
    return round(total / len(buckets))


def scenario():
    #cap.text1 = "RUNDA 1"
    #cap.text2 = "Hello Illectricity, tell me how you're doin'"
    cap.showscore = 1
    #switchstate(0,'elevate')
    #yield
    #switchstate(0,'illectricity')
    #yield
    #switchstate(0,'share')
    #yield
    #switchstate(0,'terraneo')
    #yield
    #cap.text2 = "Rezultati"
    #switchstate(0,'total')
    #yield

    cap.text1 = "RUNDA 2"
    cap.text2 = "Dare To Be Original"
    switchstate(1,'elevate')
    yield
    switchstate(1,'illectricity')
    yield
    switchstate(1,'share')
    yield
    switchstate(1,'terraneo')
    yield
    cap.text2 = "Rezultati"
    switchstate(1,'total')
    yield

    cap.text1 = "RUNDA 3"
    cap.text2 = "Mashed Potatos"
    switchstate(2,'share')
    yield
    switchstate(2,'terraneo')
    yield
    switchstate(2,'elevate')
    yield
    switchstate(2,'illectricity')
    yield
    cap.text2 = "Rezultati"
    switchstate(2,'total')
    yield

    cap.text1 = "RUNDA 4"
    cap.text2 = "BASStardz"
    switchstate(3,'terraneo')
    yield
    switchstate(3,'share')
    yield
    switchstate(3,'illectricity')
    yield
    switchstate(3,'elevate')
    yield
    cap.text2 = "Rezultati"
    switchstate(3,'total')
    yield

    cap.text1 = "RUNDA 5"
    cap.text2 = "Pop That Coochie"
    switchstate(4,'illectricity')
    yield
    switchstate(4,'elevate')
    yield
    switchstate(4,'terraneo')
    yield
    switchstate(4,'share')
    yield
    cap.text2 = "Rezultati"
    switchstate(4,'total')
    yield
    cap.text1 = "UKUPNI REZULTATI"
    cap.text2 = ""

    cap.valuesoverride = { 'terraneo': averagebuckets(teams['terraneo'].values()),
                           'illectricity': averagebuckets(teams['illectricity'].values()),
                           'share': averagebuckets(teams['share'].values()),
                           'elevate': averagebuckets(teams['elevate'].values()) }

    yield
    cap.showscore = 0
    cap.text1 = "RUNDA 6"
    cap.text2 = "WINNER'S ROUND"

ivor = TcpClient("10.10.10.2",43210)

def send():
    data = show()
    try:
        ivor.tx(data)
    except (err):
        ivor.reconnect()


def sendloop():
    while True:
        send()
        time.sleep(0.1)

thread.start_new_thread(sendloop, ())


def pause():
    switchstate(0,'total')
