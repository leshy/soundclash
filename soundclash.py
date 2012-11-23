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

    def tickloop(self,seconds,bucket):
        self.tick()
        start = time.time()
        while ((time.time() - start) < seconds):
            bucket.feed(self.tick())

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



buckets = {}

class AvgBucket():
    def __init__(self,name):
        self.value = 0
        self.num = 333
        self.name = name
        buckets[self.name] = self

    def feed(self,value):
        self.num = self.num + 1
        self.value * (1 / self.num)
        chunk = (1.0 / self.num)
        self.value = self.value * chunk * (self.num - 1)
        self.value = self.value + chunk * value


ivor = TcpClient("10.10.5.109",43210)


def show():
    data = {}
    for name in buckets:
        data[name] = int(buckets[name].value)

    return data

def send():
    ivor.tx(show())

def sendloop():
    while True:
        send()
        time.sleep(1)

thread.start_new_thread(sendloop, ())

class videoCore():
    def __init__(self):
        easycap = Device(1)
        self.camera1 = Camera(self,easycap,1)
        self.camera2 = Camera(self,easycap,2)
        self.windowtime = 10

    def start(self):
        thread.start_new_thread(self.loop, ())

    def loop(self):
        while True:
            self.camera1.tickloop(self.windowtime,self.bucket)
            self.camera2.tickloop(self.windowtime,self.bucket)

cap = videoCore()
cap.bucket = AvgBucket('bla')
cap.start()

def bucket(name):
    if not buckets.has_key(name):
        AvgBucket(name)

    cap.bucket = buckets[name]
