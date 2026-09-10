#!/usr/bin/python3
# 
# Copyright 2017 ghostop14
# 
# This is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3, or (at your option)
# any later version.
# 
# This software is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License
# along with this software; see the file COPYING.  If not, write to
# the Free Software Foundation, Inc., 51 Franklin Street,
# Boston, MA 02110-1301, USA.
# 

import os
import shutil
import subprocess
import re
import datetime
from dateutil import parser
import json
import copy
from time import sleep
from sparrowgps import SparrowGPS
from sparrowcommon import stringtobool

# ------------------  Global channel to frequency definitions ------------------------------
channelToFreq = {}
channelToFreq['1'] = '2412'
channelToFreq['2'] = '2417'
channelToFreq['3'] = '2422'
channelToFreq['4'] = '2427'
channelToFreq['5'] = '2432'
channelToFreq['6'] = '2437'
channelToFreq['7'] = '2442'
channelToFreq['8'] = '2447'
channelToFreq['9'] = '2452'
channelToFreq['10'] = '2457'
channelToFreq['11'] = '2462'
channelToFreq['12'] = '2467'
channelToFreq['13'] = '2472'
channelToFreq['14'] = '2484'

channelToFreq['16'] = '5080'
channelToFreq['34'] = '5170'
channelToFreq['36'] = '5180'
channelToFreq['38'] = '5190'
channelToFreq['40'] = '5200'
channelToFreq['42'] = '5210'
channelToFreq['44'] = '5220'
channelToFreq['46'] = '5230'
channelToFreq['48'] = '5240'
channelToFreq['50'] = '5250'
channelToFreq['52'] = '5260'
channelToFreq['54'] = '5270'
channelToFreq['56'] = '5280'
channelToFreq['58'] = '5290'
channelToFreq['60'] = '5300'
channelToFreq['62'] = '5310'
channelToFreq['64'] = '5320'
channelToFreq['100'] = '5500'
channelToFreq['102'] = '5510'
channelToFreq['104'] = '5520'
channelToFreq['106'] = '5530'
channelToFreq['108'] = '5540'
channelToFreq['110'] = '5550'
channelToFreq['112'] = '5560'
channelToFreq['114'] = '5570'
channelToFreq['116'] = '5580'
channelToFreq['118'] = '5590'
channelToFreq['120'] = '5600'
channelToFreq['122'] = '5610'
channelToFreq['124'] = '5620'
channelToFreq['126'] = '5630'
channelToFreq['128'] = '5640'
channelToFreq['132'] = '5660'
channelToFreq['134'] = '5670'
channelToFreq['136'] = '5680'
channelToFreq['138'] = '5690'
channelToFreq['140'] = '5700'
channelToFreq['142'] = '5710'
channelToFreq['144'] = '5720'
channelToFreq['149'] = '5745'
channelToFreq['151'] = '5755'
channelToFreq['153'] = '5765'
channelToFreq['155'] = '5775'
channelToFreq['157'] = '5785'
channelToFreq['159'] = '5795'
channelToFreq['161'] = '5805'
channelToFreq['165'] = '5825'
channelToFreq['169'] = '5845'
channelToFreq['173'] = '5865'
channelToFreq['183'] = '4915'
channelToFreq['184'] = '4920'
channelToFreq['185'] = '4925'
channelToFreq['187'] = '4935'
channelToFreq['188'] = '4940'
channelToFreq['189'] = '4945'
channelToFreq['192'] = '4960'
channelToFreq['196'] = '4980'

freqToChannel = {v: k for k, v in channelToFreq.items()}

# ------------------  Interface detection -------------------------------------
# Cached result of which tool is available for listing wireless interfaces.
# None means not yet determined. Set on first call to getInterfaces().
interfaceApp = None

_INTERFACE_APPS = [
    # (executable, full command, regex to extract interface names)
    ('iw',       ['iw', 'dev'],                                              r'Interface\s+([a-zA-Z0-9_\-]+)'),
    ('iwconfig', ['iwconfig'],                                               r'^([a-zA-Z0-9_\-]+)\s+.*(?:IEEE|Mode:|ESSID)'),
    ('nmcli',    ['nmcli', '--colors', 'no', '--terse', 'device', 'status'], r'^([a-zA-Z0-9_\-]+):wifi:'),
]

def _findInterfaceApp():
    """Return the first available interface-listing tool as (cmd, pattern), or None."""
    for exe, cmd, pattern in _INTERFACE_APPS:
        if shutil.which(exe):
            return (cmd, pattern)
    return None


# Cached iwconfig-vs-iw selection for callsites that cannot use nmcli
# (monitor-mode enumeration, channel set). iwconfig is preferred when present
# for behavioral parity with older releases; iw is the fallback on systems
# where iwconfig has been removed (Ubuntu 25.04+, etc).
_iwTool = None

def findIwTool():
    """Return 'iwconfig' if available, else 'iw' if available, else None."""
    global _iwTool
    if _iwTool is None:
        if shutil.which('iwconfig'):
            _iwTool = 'iwconfig'
        elif shutil.which('iw'):
            _iwTool = 'iw'
    return _iwTool

# ------------------  WirelessNetwork class ------------------------------------
class WirelessClient(object):
    def __init__(self):
        self.macAddr = ""
        self.apMacAddr = ""
        self.ssid = ""
        self.channel = 0
        self.signal = -1000 # dBm
        now=datetime.datetime.now()
        self.firstSeen = now
        self.lastSeen = now

        self.gps = SparrowGPS()
        self.strongestsignal = self.signal
        self.strongestgps = SparrowGPS()

        self.probedSSIDs = []
        # Used for tracking in network table
        self.foundInList = False
        
    def __str__(self):
        retVal = ""
        
        retVal += "MAC Address: " + self.macAddr + "\n"
        retVal += "Associated Access Point Mac Address: " + self.apMacAddr + "\n"
        retVal += "SSID: " + self.ssid + "\n"
        retVal += "Channel: " + str(self.channel) + "\n"
        retVal += "Signal: " + str(self.signal) + " dBm\n"
        retVal += "Strongest Signal: " + str(self.strongestsignal) + " dBm\n"
        retVal += "First Seen: " + str(self.firstSeen) + "\n"
        retVal += "Last Seen: " + str(self.lastSeen) + "\n"
        retVal += "Probed SSIDs:"
        
        if (len(self.probedSSIDs) > 0):
            for curSSID in self.probedSSIDs:
                retVal += " " + curSSID
                
            retVal += "\n"
        else:
            retVal += " No probes observed\n"
            
        retVal += "Last GPS:\n"
        retVal += str(self.gps)
        retVal += "Strongest GPS:\n"
        retVal += str(self.strongestgps)
            
        return retVal
        
    def copy(self):
        return copy.deepcopy(self)
        
    def __eq__(self, obj):
        # This is equivance....   ==
        if not isinstance(obj, WirelessClient):
           return False
          
        if self.macAddr != obj.macAddr:
            return False
            
        if self.apMacAddr != obj.apMacAddr:
            return False

        return True

    def __ne__(self, other):
            return not self.__eq__(other)
        
    def getKey(self):
        return self.macAddr
        
    def associated(self):
        if len(self.apMacAddr) == 0 or (self.apMacAddr == "(not associated)"):
            return False
            
        return True
        
    def createFromJsonDict(jsondict):
        retVal = WirelessClient()
        retVal.fromJsondict(jsondict)
        return retVal
        
    def fromJsondict(self, dictjson):
        # Note: if the json dictionary isn't correct, this will naturally throw an exception that may
        # need to be caught for error detection
        self.macAddr = dictjson['macAddr']
        self.apMacAddr = dictjson['apMacAddr']
        self.ssid = dictjson['ssid']
        self.channel = int(dictjson['channel'])
        
        self.signal = int(dictjson['signal'])
        self.strongestsignal = int(dictjson['strongestsignal'])

        self.firstSeen = parser.parse(dictjson['firstseen'])
        self.lastSeen = parser.parse(dictjson['lastseen'])

        self.gps.latitude = float(dictjson['lat'])
        self.gps.longitude = float(dictjson['lon'])
        self.gps.altitude = float(dictjson['alt'])
        self.gps.speed = float(dictjson['speed'])
        self.gps.isValid = stringtobool(dictjson['gpsvalid'])
        
        self.strongestgps.latitude = float(dictjson['strongestlat'])
        self.strongestgps.longitude = float(dictjson['strongestlon'])
        self.strongestgps.altitude = float(dictjson['strongestalt'])
        self.strongestgps.speed = float(dictjson['strongestspeed'])
        self.strongestgps.isValid = stringtobool(dictjson['strongestgpsvalid'])
        
        self.probedSSIDs = dictjson['probedssids']
            
    def fromJson(self, jsonstr):
        dictjson = json.loads(jsonstr)
        self.fromJsondict(dictjson)
            
    def toJson(self):
        dictjson = self.toJsondict()
        return json.dumps(dictjson)
        
    def toJsondict(self):
        dictjson = {}
        dictjson['type'] = 'wifi-client'
        dictjson['macAddr'] = self.macAddr
        dictjson['apMacAddr'] = self.apMacAddr
        dictjson['ssid'] = self.ssid
        dictjson['channel'] = self.channel
        dictjson['signal'] = self.signal
        dictjson['firstseen'] = str(self.firstSeen)
        dictjson['lastseen'] = str(self.lastSeen)
        dictjson['lat'] = str(self.gps.latitude)
        dictjson['lon'] = str(self.gps.longitude)
        dictjson['alt'] = str(self.gps.altitude)
        dictjson['speed'] = str(self.gps.speed)
        dictjson['gpsvalid'] = str(self.gps.isValid)
        
        dictjson['strongestsignal'] = self.strongestsignal
        dictjson['strongestlat'] = str(self.strongestgps.latitude)
        dictjson['strongestlon'] = str(self.strongestgps.longitude)
        dictjson['strongestalt'] = str(self.strongestgps.altitude)
        dictjson['strongestspeed'] = str(self.strongestgps.speed)
        dictjson['strongestgpsvalid'] = str(self.strongestgps.isValid)

        dictjson['probedssids'] = self.probedSSIDs
        
        return dictjson
        
class WirelessNetwork(object):
    ERR_NETDOWN = 156
    ERR_OPNOTSUPPORTED = 161
    ERR_DEVICEBUSY = 240
    ERR_OPNOTPERMITTED = 255
    
    def __init__(self):
        self.macAddr = ""
        self.ssid = ""
        self.mode = "" # master, managed, monitor, etc.
        self.security = "Open" # on or off
        self.privacy = "None" # group cipher
        self.cipher = ""  # pairwise cipher
        self.channel = 0   # Channel #
        self.frequency = 0
        self.signal = -1000 # dBm
        self.stationcount = -1
        self.utilization = -1.0
        self.bandwidth = 20 # Default to 20.  we'll bump it up as we see params.  max BW in any protocol 20 or 40 or 80 or 160 MHz
        self.secondaryChannel = 0  # used for 40+ MHz
        self.thirdChannel = 0  # used for 80+ MHz channels
        self.secondaryChannelLocation = ''  # above/below
        now=datetime.datetime.now()
        self.firstSeen = now
        self.lastSeen = now
        self.beaconCount = 0
        self.gps = SparrowGPS()
        self.strongestsignal = self.signal
        self.strongestgps = SparrowGPS()
        
        # Used for tracking in network table
        self.foundInList = False
        
        super().__init__()

    def __str__(self):
        retVal = ""
        
        retVal += "MAC Address: " + self.macAddr + "\n"
        retVal += "SSID: " + self.ssid + "\n"
        retVal += "Mode: " + self.mode + "\n"
        retVal += "Security: " + self.security + "\n"
        retVal += "Privacy: " + self.privacy + "\n"
        retVal += "Cipher: " + self.cipher + "\n"
        retVal += "Frequency: " + str(self.frequency) + " MHz\n"
        retVal += "Channel: " + str(self.channel) + "\n"
        retVal += "Secondary Channel: " + str(self.secondaryChannel) + "\n"
        retVal += "Secondary Channel Location: " + self.secondaryChannelLocation + "\n"
        retVal += "Third Channel: " + str(self.thirdChannel) + "\n"
        retVal += "Signal: " + str(self.signal) + " dBm\n"
        retVal += "Station Count: " + str(self.stationcount) + "\n"
        retVal += "Utilization: " + str(self.utilization) + "\n"
        retVal += "Strongest Signal: " + str(self.strongestsignal) + " dBm\n"
        retVal += "Bandwidth: " + str(self.bandwidth) + "\n"
        retVal += "Beacons: " + str(self.beaconCount) + "\n"
        retVal += "First Seen: " + str(self.firstSeen) + "\n"
        retVal += "Last Seen: " + str(self.lastSeen) + "\n"
        retVal += "Last GPS:\n"
        retVal += str(self.gps)
        retVal += "Strongest GPS:\n"
        retVal += str(self.strongestgps)

        return retVal

    def copy(self):
        return copy.deepcopy(self)
        
    def __eq__(self, obj):
        # This is equivance....   ==
        if not isinstance(obj, WirelessNetwork):
           return False
          
        if self.macAddr != obj.macAddr:
            return False
        if self.ssid != obj.ssid:
            return False

        if self.mode != obj.mode:
            return False
            
        if self.security != obj.security:
            return False
            
        if self.channel != obj.channel:
            return False
            
        return True

    def __ne__(self, other):
            return not self.__eq__(other)
        
    def createFromJsonDict(jsondict):
        retVal = WirelessNetwork()
        retVal.fromJsondict(jsondict)
        return retVal
        
    def fromJsondict(self, dictjson):
        # Note: if the json dictionary isn't correct, this will naturally throw an exception that may
        # need to be caught for error detection
        self.macAddr = dictjson['macAddr']
        self.ssid = dictjson['ssid']
        self.mode = dictjson['mode']
        self.security = dictjson['security']
        self.privacy = dictjson['privacy']
        self.cipher = dictjson['cipher']
        self.frequency = int(dictjson['frequency'])
        self.channel = int(dictjson['channel'])
        self.secondaryChannel = int(dictjson['secondaryChannel'])
        self.secondaryChannelLocation = dictjson['secondaryChannelLocation']
        self.thirdChannel = int(dictjson['thirdChannel'])
        self.signal = int(dictjson['signal'])
        if 'stationcount' in dictjson.keys():
            self.stationcount = int(dictjson['stationcount'])
        else:
            self.stationcount = -1
            
        self.utilization = float(dictjson['utilization'])
        self.strongestsignal = int(dictjson['strongestsignal'])
        self.bandwidth = int(dictjson['bandwidth'])
        self.beaconCount = int(dictjson.get('beaconCount', 0))
        self.firstSeen = parser.parse(dictjson['firstseen'])
        self.lastSeen = parser.parse(dictjson['lastseen'])
        self.gps.latitude = float(dictjson['lat'])
        self.gps.longitude = float(dictjson['lon'])
        self.gps.altitude = float(dictjson['alt'])
        self.gps.speed = float(dictjson['speed'])
        self.gps.isValid = stringtobool(dictjson['gpsvalid'])
        
        self.strongestgps.latitude = float(dictjson['strongestlat'])
        self.strongestgps.longitude = float(dictjson['strongestlon'])
        self.strongestgps.altitude = float(dictjson['strongestalt'])
        self.strongestgps.speed = float(dictjson['strongestspeed'])
        self.strongestgps.isValid = stringtobool(dictjson['strongestgpsvalid'])
            
    def fromJson(self, jsonstr):
        dictjson = json.loads(jsonstr)
        self.fromJsondict(dictjson)
            
    def toJsondict(self):
        dictjson = {}
        dictjson['type'] = 'wifi-ap'
        dictjson['macAddr'] = self.macAddr
        dictjson['ssid'] = self.ssid
        dictjson['mode'] = self.mode
        dictjson['security'] = self.security
        dictjson['privacy'] = self.privacy
        dictjson['cipher'] = self.cipher
        dictjson['frequency'] = self.frequency
        dictjson['channel'] = self.channel
        dictjson['secondaryChannel'] = self.secondaryChannel
        dictjson['secondaryChannelLocation'] = self.secondaryChannelLocation
        dictjson['thirdChannel'] = self.thirdChannel
        dictjson['signal'] = self.signal
        dictjson['stationcount'] = self.stationcount
        dictjson['utilization'] = self.utilization

        dictjson['strongestsignal'] = self.strongestsignal
        dictjson['bandwidth'] = self.bandwidth
        dictjson['beaconCount'] = self.beaconCount
        dictjson['firstseen'] = str(self.firstSeen)
        dictjson['lastseen'] = str(self.lastSeen)
        dictjson['lat'] = str(self.gps.latitude)
        dictjson['lon'] = str(self.gps.longitude)
        dictjson['alt'] = str(self.gps.altitude)
        dictjson['speed'] = str(self.gps.speed)
        dictjson['gpsvalid'] = str(self.gps.isValid)
        
        dictjson['strongestlat'] = str(self.strongestgps.latitude)
        dictjson['strongestlon'] = str(self.strongestgps.longitude)
        dictjson['strongestalt'] = str(self.strongestgps.altitude)
        dictjson['strongestspeed'] = str(self.strongestgps.speed)
        dictjson['strongestgpsvalid'] = str(self.strongestgps.isValid)
        
        return dictjson
        
    def toJson(self):
        dictjson = self.toJsondict()
        return json.dumps(dictjson)
        
    def getChannelString(self):
        if self.bandwidth == 40 and self.secondaryChannel > 0:
            retVal = str(self.channel) + '+' + str(self.secondaryChannel)
        else:
            retVal = str(self.channel)
            
        return retVal
        
    def getKey(self):
        return (self.macAddr or "").upper() + (self.ssid or "") + str(self.channel)
        
# Module-level compiled regex patterns for parseIWoutput() — compiled once, not per-call
_P_BSS = re.compile(r'^BSS (.*?)\(')
_P_SSID = re.compile('^.+?SSID: +(.*)')
_P_ESS = re.compile('^	capability:.*(ESS)')
_P_ESS_PRIVACY = re.compile('^	capability:.*(ESS Privacy)')
_P_IBSS = re.compile('^	capability:.*(IBSS)')
_P_IBSS_PRIVACY = re.compile('^	capability:.*(IBSS Privacy)')
_P_AUTH_SUITES = re.compile('.*?Authentication suites: *(.*)')
_P_PW_CIPHERS = re.compile('.*?Pairwise ciphers: *(.*)')
_P_PARAM_CHANNEL = re.compile('^.*?DS Parameter set: channel +([0-9]+).*')
_P_PRIMARY_CHANNEL = re.compile('^.*?primary channel: +([0-9]+).*')
_P_FREQ = re.compile('^.*?freq:.*?([0-9]+).*')
_P_SIGNAL = re.compile(r'^.*?signal:.*?([\-0-9]+).*?dBm')
_P_HT = re.compile('.*?HT20/HT40.*')
_P_BW = re.compile('.*?\\* channel width:.*?([0-9]+) MHz.*')
_P_SECONDARY = re.compile('^.*?secondary channel offset: *([^ \\t]+).*')
_P_THIRDFREQ = re.compile('^.*?center freq segment 1: *([^ \\t]+).*')
_P_STATIONCOUNT = re.compile('.*station count: ([0-9]+)')
_P_UTILIZATION = re.compile('.*channel utilisation: ([0-9]+)/255')

class WirelessEngine(object):
    def __init__(self):
        super().__init__()

    def getMacAddress(interface):
        macaddr = ""
        
        try:
            f = open('/sys/class/net/'+interface+'/address', 'r')
            macaddr = f.readline().strip()
            f.close()
        except:
            pass
            
        return macaddr
        
    def getFrequencyForChannel(channelNumber):
        channelStr = str(channelNumber)
        if channelStr in channelToFreq:
            return channelToFreq[channelStr]
        else:
            return None
            
    def getSignalQualityFromDB0To5(dBm):
        # Based on same scale tha Microsoft uses.
        # See https://stackoverflow.com/questions/15797920/how-to-convert-wifi-signal-strength-from-quality-percent-to-rssi-dbm
        if (dBm <= -100):
            quality = 0
        elif dBm >= -50:
            quality = 100
        else:
            quality = 2 * (dBm + 100)      
        
        return int(4*quality/100)

    def getSignalQualityFromDB(dBm):
        # Based on same scale tha Microsoft uses.
        # See https://stackoverflow.com/questions/15797920/how-to-convert-wifi-signal-strength-from-quality-percent-to-rssi-dbm
        if (dBm <= -100):
            quality = 0
        elif dBm >= -50:
            quality = 100
        else:
            quality = 2 * (dBm + 100)      
        
        return quality

    def convertUnknownToString(ssid):
        if '\\x00' not in ssid:
            return ssid
            
        retVal = ssid.replace('\\x00', '')
        numblanks = ssid.count('\\x00')
        
        if len(retVal) == 0:
            if numblanks > 0:
                return '<Unknown (' + str(numblanks )+ ')>'
            else:
                return '<Unknown>'
        else:
            return ssid
        
    def getInterfaces(printResults=False) -> list:
        """ Returns a list of wireless interfaces using iw, iwconfig, or nmcli.
            Interfaces that are UP / connected are listed first.
        """
        global interfaceApp
        if interfaceApp is None:
            interfaceApp = _findInterfaceApp()

        retVal = []

        if interfaceApp is None:
            if printResults:
                print("Error: No wireless interface tool (iw/iwconfig/nmcli) found.")
            return retVal

        cmd, pattern = interfaceApp
        try:
            result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5)
            wireless_result = result.stdout.decode('UTF-8', errors='ignore')
            tmpInterfaces = re.findall(pattern, wireless_result, re.MULTILINE)
        except Exception:
            tmpInterfaces = []

        if tmpInterfaces:
            seen = set()
            for curInterface in tmpInterfaces:
                tmpStr = curInterface.replace(' ', '').strip()
                if tmpStr and tmpStr not in seen:
                    seen.add(tmpStr)
                    retVal.append(tmpStr)

            def _iface_priority(iface_name):
                try:
                    with open(f"/sys/class/net/{iface_name}/operstate", "r") as f:
                        state = f.read().strip().lower()
                        return 0 if state == "up" else 1
                except Exception:
                    return 2

            retVal.sort(key=_iface_priority)

            if printResults:
                for iface in retVal:
                    print(iface)
        else:
            if printResults:
                print("Error: No wireless interfaces found.")

        return retVal

    def getMonitoringModeInterfaces(printResults=False):
        # Note: for standard scans with iw, this isn't required.  Just root access.
        # This is only required for some of the more advanced pen testing capabilities
        tool = findIwTool()
        retVal = []

        if tool is None:
            if printResults:
                print("Error: Neither iwconfig nor iw is available.")
            return retVal

        if tool == 'iwconfig':
            result = subprocess.run(['iwconfig'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            wirelessResult = result.stdout.decode('UTF-8')
            p = re.compile('^(.*?) IEEE.*?Mode:Monitor', re.MULTILINE)
            tmpInterfaces = p.findall(wirelessResult)

            if (len(tmpInterfaces) > 0):
                for curInterface in tmpInterfaces:
                    tmpStr=curInterface.replace(' ','')
                    retVal.append(tmpStr)
                    # debug
                    if (printResults):
                        print(tmpStr)
            else:
                # If we're on a pi or the driver is weird, it may not put IEEE and Mode:Monitor on the same line.
                monLine = -1
                i = 0
                lines = wirelessResult.split('\n')
                for curLine in lines:
                    if 'Mode:Monitor' in curLine:
                        monLine = i - 1
                        break
                    else:
                        i = i + 1
                if monLine > -1:
                    p = re.compile('^(.*?) .*', re.MULTILINE)
                    tmpInterfaces = p.findall(lines[monLine])
                    if (len(tmpInterfaces) > 0):
                        for curInterface in tmpInterfaces:
                            tmpStr=curInterface.replace(' ','')
                            retVal.append(tmpStr)
        else:
            # 'iw dev' output: blocks of "Interface <name>" followed by lines
            # including "type monitor" for monitor-mode interfaces.
            result = subprocess.run(['iw', 'dev'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
            current = None
            for line in result.stdout.decode('UTF-8').splitlines():
                stripped = line.strip()
                if stripped.startswith('Interface '):
                    current = stripped.split(None, 1)[1]
                elif stripped == 'type monitor' and current:
                    retVal.append(current)
                    if printResults:
                        print(current)
                    current = None

        if len(retVal) == 0 and printResults:
            print("Error: No monitoring mode wireless interfaces found.")

        return retVal

    def getNetworksAsJson(interfaceName, gpsData, huntChannelList=None):
        # This is only used by the remote agent to get and return networks
        if (huntChannelList is None) or (len(huntChannelList) == 0):
            # This code handles the thought that "what if we query for networks and the interface
            # reports busy (it does happen if we query too fast.)
            retries = 0
            retCode = WirelessNetwork.ERR_DEVICEBUSY
            
            while (retCode == WirelessNetwork.ERR_DEVICEBUSY) and (retries < 3):
                # Handle retries in case we get a busy response
                retCode, errString, wirelessNetworks = WirelessEngine.scanForNetworks(interfaceName)
                retries += 1
                if retCode == WirelessNetwork.ERR_DEVICEBUSY:
                    sleep(0.4)
        else:
            wirelessNetworks = {}
            for curFrequency in huntChannelList:
                # Handle if the device reports busy with some retries
                retries = 0
                retCode = WirelessNetwork.ERR_DEVICEBUSY
                while (retCode == WirelessNetwork.ERR_DEVICEBUSY) and (retries < 3):
                    # Handle retries in case we get a busy response
                    retCode, errString, tmpWirelessNetworks = WirelessEngine.scanForNetworks(interfaceName,curFrequency )
                    retries += 1
                    if retCode == WirelessNetwork.ERR_DEVICEBUSY:
                        sleep(0.2)
                
                for curKey in tmpWirelessNetworks.keys():
                    curNet = tmpWirelessNetworks[curKey]
                    wirelessNetworks[curNet.getKey()] = tmpWirelessNetworks[curNet.getKey()]
            
        retVal = {}
        retVal['errCode'] = retCode
        retVal['errString'] = errString
        
        netList = []
        
        for curKey in wirelessNetworks.keys():
            curNet = wirelessNetworks[curKey]
            if gpsData is not None:
                curNet.gps.copy(gpsData)
            netList.append(curNet.toJsondict())
            
        gpsdict = {}
        
        gpsloc = SparrowGPS()
        if (gpsData is not None):
            gpsloc.copy(gpsData)
        
        gpsdict['latitude'] = gpsloc.latitude
        gpsdict['longitude'] = gpsloc.longitude
        gpsdict['altitude'] = gpsloc.altitude
        gpsdict['speed'] = gpsloc.speed
        retVal['gps'] = gpsdict
        
        retVal['networks'] = netList
        
        jsonstr = json.dumps(retVal)
        
        return retCode, errString, jsonstr
        
    @staticmethod
    def ensureInterfaceUp(interfaceName):
        """Attempts to bring interface UP if currently down."""
        try:
            operstate_path = f"/sys/class/net/{interfaceName}/operstate"
            if os.path.exists(operstate_path):
                with open(operstate_path, "r") as f:
                    state = f.read().strip().lower()
                if state == "down":
                    subprocess.run(['ip', 'link', 'set', interfaceName, 'up'],
                                   stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        except Exception:
            pass

    @staticmethod
    def getInterfaceMode(interfaceName):
        """Returns 'monitor', 'managed', or 'unknown' for the interface."""
        try:
            res = subprocess.run(['iw', 'dev', interfaceName, 'info'],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=2)
            if res.returncode == 0:
                for line in res.stdout.decode('utf-8', errors='ignore').splitlines():
                    line_s = line.strip()
                    if line_s.startswith('type monitor'):
                        return 'monitor'
                    elif line_s.startswith('type managed'):
                        return 'managed'
        except Exception:
            pass

        try:
            res = subprocess.run(['iwconfig', interfaceName],
                                 stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=2)
            if res.returncode == 0:
                out = res.stdout.decode('utf-8', errors='ignore')
                if 'Mode:Monitor' in out:
                    return 'monitor'
                elif 'Mode:Managed' in out:
                    return 'managed'
        except Exception:
            pass

        try:
            type_file = f"/sys/class/net/{interfaceName}/type"
            if os.path.exists(type_file):
                with open(type_file, 'r') as f:
                    val = f.read().strip()
                    if val in ('801', '802', '803'):
                        return 'monitor'
                    elif val == '1':
                        return 'managed'
        except Exception:
            pass

        return 'unknown'

    @staticmethod
    def isMonitorMode(interfaceName):
        """Checks if interface is in monitor mode."""
        return WirelessEngine.getInterfaceMode(interfaceName) == 'monitor'

    @staticmethod
    def getInterfaceDriver(interfaceName):
        """Returns the kernel driver module name for the given network interface."""
        try:
            driver_path = f"/sys/class/net/{interfaceName}/device/driver"
            if os.path.islink(driver_path):
                return os.path.basename(os.readlink(driver_path))
        except OSError:
            pass
        return ""

    @staticmethod
    def setInterfaceMode(interfaceName, targetMode):
        """Switches interface between 'monitor' and 'managed' mode.
        Supports both direct in-place switching and driver-aware VIF switching
        (e.g., creating wlan0mon for iwlwifi, which silently drops frames in direct monitor mode).
        Returns (success: bool, message: str).
        """
        if targetMode not in ('monitor', 'managed'):
            return False, f"Unsupported mode: {targetMode}"

        current = WirelessEngine.getInterfaceMode(interfaceName)
        if current == targetMode:
            return True, f"Interface {interfaceName} is already in {targetMode} mode."

        driver = WirelessEngine.getInterfaceDriver(interfaceName)

        def _run_cmd(cmd):
            # Try direct execution
            r = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=6)
            if r.returncode == 0:
                return True, ""
            # Try passwordless sudo
            r = subprocess.run(['sudo', '-n'] + cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=6)
            if r.returncode == 0:
                return True, ""
            # Try pkexec if desktop GUI session
            if os.environ.get('DISPLAY') or os.environ.get('WAYLAND_DISPLAY'):
                r = subprocess.run(['pkexec'] + cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, timeout=8)
                if r.returncode == 0:
                    return True, ""
            err = r.stderr.decode('utf-8', errors='ignore').strip()
            return False, err

        def _get_phy(iface):
            try:
                out = subprocess.run(['iw', 'dev', iface, 'info'], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL).stdout.decode('utf-8')
                for line in out.splitlines():
                    if 'wiphy' in line:
                        return f"phy{line.strip().split()[-1]}"
            except Exception:
                pass
            return None

        if targetMode == 'monitor':
            _run_cmd(['nmcli', 'dev', 'set', interfaceName, 'managed', 'no'])

            # Driver-aware VIF method for iwlwifi (Intel AX201, etc.)
            if driver == 'iwlwifi':
                mon_iface = f"{interfaceName}mon"
                phy = _get_phy(interfaceName) or "phy1"
                _run_cmd(['iw', 'dev', mon_iface, 'del'])
                _run_cmd(['ip', 'link', 'set', interfaceName, 'down'])
                _run_cmd(['iw', 'dev', interfaceName, 'del'])
                ok, err = _run_cmd(['iw', phy, 'interface', 'add', mon_iface, 'type', 'monitor'])
                if not ok:
                    return False, f"Failed to add monitor VIF {mon_iface}: {err}"
                _run_cmd(['ip', 'link', 'set', mon_iface, 'up'])
                _run_cmd(['iw', 'dev', mon_iface, 'set', 'channel', '1'])
                return True, f"Monitor interface {mon_iface} created successfully."

            # Standard in-place switch for other adapters
            _run_cmd(['ip', 'link', 'set', interfaceName, 'down'])
            ok, err = _run_cmd(['iw', 'dev', interfaceName, 'set', 'type', 'monitor'])
            if not ok:
                return False, f"Failed to set type monitor on {interfaceName}: {err}"
            _run_cmd(['ip', 'link', 'set', interfaceName, 'up'])
            _run_cmd(['iw', 'dev', interfaceName, 'set', 'channel', '1'])
            return True, f"Switched {interfaceName} to monitor mode."

        else:  # targetMode == 'managed'
            if interfaceName.endswith('mon'):
                base_iface = interfaceName[:-3]
                phy = _get_phy(interfaceName) or "phy1"
                _run_cmd(['iw', 'dev', interfaceName, 'del'])
                if not os.path.exists(f"/sys/class/net/{base_iface}"):
                    _run_cmd(['iw', phy, 'interface', 'add', base_iface, 'type', 'managed'])
                _run_cmd(['ip', 'link', 'set', base_iface, 'up'])
                _run_cmd(['nmcli', 'dev', 'set', base_iface, 'managed', 'yes'])
                return True, f"Restored {base_iface} to managed mode."

            # Standard in-place restore
            _run_cmd(['ip', 'link', 'set', interfaceName, 'down'])
            ok, err = _run_cmd(['iw', 'dev', interfaceName, 'set', 'type', 'managed'])
            if not ok:
                return False, f"Failed to set type managed on {interfaceName}: {err}"
            _run_cmd(['ip', 'link', 'set', interfaceName, 'up'])
            _run_cmd(['nmcli', 'dev', 'set', interfaceName, 'managed', 'yes'])
            return True, f"Restored {interfaceName} to managed mode."


    @staticmethod
    def parseNmcliOutput(nmcliOutput, filterFrequency=0):
        """Parse nmcli dev wifi list terse output into WirelessNetwork dict."""
        retVal = {}
        now = datetime.datetime.now()
        for line in nmcliOutput.splitlines():
            line = line.strip()
            if not line:
                continue
            parts = re.split(r'(?<!\\):', line)
            if len(parts) >= 8:
                bssid = parts[1].replace(r'\:', ':').strip()
                if not bssid or bssid == '--':
                    continue
                ssid = parts[2].replace(r'\:', ':').strip()
                mode = parts[3].replace(r'\:', ':').strip()
                chan_str = parts[4].replace(r'\:', ':').strip()
                freq_str = parts[5].replace(r'\:', ':').strip()
                sig_str = parts[7].replace(r'\:', ':').strip()
                sec_str = parts[8].replace(r'\:', ':').strip() if len(parts) > 8 else ""

                curNet = WirelessNetwork()
                curNet.macAddr = bssid.upper()
                curNet.ssid = WirelessEngine.convertUnknownToString(ssid) if ssid else "<Hidden>"
                curNet.mode = "AP" if "Infra" in mode else (mode if mode else "AP")
                try:
                    curNet.channel = int(chan_str)
                except ValueError:
                    curNet.channel = 0

                freq_clean = re.sub(r'[^0-9]', '', freq_str)
                try:
                    curNet.frequency = int(freq_clean)
                except ValueError:
                    if str(curNet.channel) in channelToFreq:
                        curNet.frequency = int(channelToFreq[str(curNet.channel)])

                if filterFrequency > 0 and curNet.frequency > 0 and curNet.frequency != filterFrequency:
                    continue

                try:
                    sig_pct = int(sig_str)
                    curNet.signal = int(sig_pct / 2) - 100
                except ValueError:
                    curNet.signal = -100
                curNet.strongestsignal = curNet.signal

                sec_clean = sec_str.replace(r'\:', ':').strip()
                curNet.security = sec_clean if sec_clean else "Open"
                curNet.privacy = sec_clean if sec_clean else ""
                curNet.firstSeen = now
                curNet.lastSeen = now

                if curNet.channel > 0 or curNet.frequency > 0:
                    retVal[curNet.getKey()] = curNet

        return retVal

    @staticmethod
    def scanViaNmcli(interfaceName=None, frequency=0):
        """Perform non-root WiFi scan using nmcli."""
        try:
            if interfaceName:
                subprocess.run(['nmcli', 'dev', 'wifi', 'rescan', 'ifname', interfaceName],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
            else:
                subprocess.run(['nmcli', 'dev', 'wifi', 'rescan'],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=2)
        except Exception:
            pass

        try:
            cmd = ['nmcli', '--terse', '--fields', 'IN-USE,BSSID,SSID,MODE,CHAN,FREQ,RATE,SIGNAL,SECURITY', 'dev', 'wifi', 'list']
            if interfaceName:
                cmd += ['ifname', interfaceName]
            res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, timeout=5)
            if res.returncode == 0:
                output = res.stdout.decode('utf-8', errors='ignore')
                return WirelessEngine.parseNmcliOutput(output, frequency)
        except Exception:
            pass
        return {}

    @staticmethod
    def scanMonitorNetworks(interfaceName, frequency=0, printResults=False):
        """Passive monitor-mode frame sniffer capturing 802.11 beacons and probe responses with channel hopping."""
        if frequency > 0:
            if str(frequency) in freqToChannel:
                channels = [int(freqToChannel[str(frequency)])]
            else:
                channels = [int(frequency)]
            dwell = 0.8
        else:
            channels = list(range(1, 14))
            dwell = 0.25

        allNetworks = {}
        now = datetime.datetime.now()

        for ch in channels:
            freq = int(channelToFreq.get(str(ch), 2412))

            # Set channel on the interface using iw / sudo -n iw
            try:
                subprocess.run(['iw', 'dev', interfaceName, 'set', 'channel', str(ch)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
            except Exception:
                pass
            try:
                subprocess.run(['sudo', '-n', 'iw', 'dev', interfaceName, 'set', 'channel', str(ch)],
                               stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL, timeout=1)
            except Exception:
                pass

            # Primary capture: tcpdump with line-buffering (-l) and timeout
            captured_lines = []
            tcpdump_cmd = ['timeout', str(dwell), 'tcpdump', '-l', '-i', interfaceName, '-c', '30',
                           '-nn', '-e', '-s', '256', 'type mgt subtype beacon or type mgt subtype probe-resp']
            try:
                res = subprocess.run(tcpdump_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                if res.stdout:
                    captured_lines = res.stdout.decode('utf-8', errors='ignore').splitlines()
            except Exception:
                pass

            if not captured_lines:
                try:
                    res = subprocess.run(['sudo', '-n'] + tcpdump_cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    if res.stdout:
                        captured_lines = res.stdout.decode('utf-8', errors='ignore').splitlines()
                except Exception:
                    pass

            if captured_lines:
                for line in captured_lines:
                    bssid_m = re.search(r'(?:BSSID:|SA:)\s*([0-9a-fA-F]{2}(?::[0-9a-fA-F]{2}){5})', line)
                    if not bssid_m:
                        continue
                    bssid = bssid_m.group(1).upper()

                    ssid_m = re.search(r'(?:Beacon|Probe Response)\s*\((.*?)\)', line)
                    ssid = ssid_m.group(1) if ssid_m else "<Hidden>"

                    sig_m = re.search(r'(-?[0-9]+)dBm\s+signal', line)
                    sig = int(sig_m.group(1)) if sig_m else -75

                    ch_m = re.search(r'CH:\s*([0-9]+)', line)
                    channel = int(ch_m.group(1)) if ch_m else ch

                    is_beacon = 'Beacon' in line
                    key = bssid + ssid + str(channel)

                    if key in allNetworks:
                        curNet = allNetworks[key]
                        if is_beacon:
                            curNet.beaconCount += 1
                        curNet.lastSeen = now
                        if sig > -100:
                            curNet.signal = sig
                            if curNet.signal > curNet.strongestsignal:
                                curNet.strongestsignal = curNet.signal
                        if ssid != "<Hidden>" and curNet.ssid == "<Hidden>":
                            curNet.ssid = WirelessEngine.convertUnknownToString(ssid)
                    else:
                        curNet = WirelessNetwork()
                        curNet.macAddr = bssid.upper()
                        curNet.ssid = WirelessEngine.convertUnknownToString(ssid)
                        curNet.mode = "AP"
                        curNet.channel = channel
                        curNet.frequency = freq
                        curNet.signal = sig
                        curNet.strongestsignal = sig
                        curNet.security = "WPA2/WPA3" if ("WPA" in line or "RSN" in line or "PRIVACY" in line) else "Open"
                        curNet.privacy = curNet.security
                        curNet.beaconCount = 1 if is_beacon else 0
                        curNet.firstSeen = now
                        curNet.lastSeen = now
                        allNetworks[key] = curNet

            # Secondary fallback: tshark with valid fields and hex SSID decoding
            elif shutil.which('tshark'):
                try:
                    cmd = [
                        'timeout', '1.0', 'tshark', '-l', '-i', interfaceName,
                        '-c', '30',
                        '-Y', 'wlan.fc.type_subtype == 8 || wlan.fc.type_subtype == 5',
                        '-T', 'fields',
                        '-e', 'wlan.bssid',
                        '-e', 'wlan.ssid',
                        '-e', 'radiotap.dbm_antsignal',
                        '-e', 'wlan_radio.channel',
                        '-e', 'wlan.fc.type_subtype',
                        '-e', 'wlan.rsn.version',
                        '-e', 'wlan.fixed.capabilities.privacy'
                    ]
                    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)
                    if res.stdout:
                        for line in res.stdout.decode('utf-8', errors='ignore').splitlines():
                            parts = line.split('\t')
                            if len(parts) < 4:
                                continue
                            raw_bssid = parts[0].strip()
                            if not raw_bssid or len(raw_bssid.split(':')) != 6:
                                continue
                            bssid = raw_bssid.upper()

                            raw_ssid = parts[1].strip() if len(parts) > 1 else ""
                            ssid = raw_ssid
                            if raw_ssid:
                                try:
                                    decoded = bytes.fromhex(raw_ssid).decode('utf-8', errors='ignore')
                                    if decoded and any(c.isalnum() for c in decoded):
                                        ssid = decoded
                                except Exception:
                                    pass
                            if not ssid:
                                ssid = "<Hidden>"

                            sig = -75
                            if len(parts) > 2 and parts[2].strip():
                                try:
                                    sig = int(parts[2].split(',')[0].strip())
                                except Exception:
                                    sig = -75

                            channel = ch
                            if len(parts) > 3 and parts[3].strip():
                                try:
                                    channel = int(parts[3].split(',')[0].strip())
                                except Exception:
                                    channel = ch

                            subtype = 8
                            if len(parts) > 4 and parts[4].strip():
                                try:
                                    val = parts[4].split(',')[0].strip()
                                    subtype = int(val, 0)
                                except Exception:
                                    subtype = 8

                            is_beacon = (subtype == 8)
                            key = bssid + ssid + str(channel)

                            if key in allNetworks:
                                curNet = allNetworks[key]
                                if is_beacon:
                                    curNet.beaconCount += 1
                                curNet.lastSeen = now
                                if sig > -100:
                                    curNet.signal = sig
                                    if curNet.signal > curNet.strongestsignal:
                                        curNet.strongestsignal = curNet.signal
                                if ssid != "<Hidden>" and curNet.ssid == "<Hidden>":
                                    curNet.ssid = WirelessEngine.convertUnknownToString(ssid)
                            else:
                                curNet = WirelessNetwork()
                                curNet.macAddr = bssid.upper()
                                curNet.ssid = WirelessEngine.convertUnknownToString(ssid)
                                curNet.mode = "AP"
                                curNet.channel = channel
                                curNet.frequency = freq
                                curNet.signal = sig
                                curNet.strongestsignal = sig
                                curNet.security = "WPA2/WPA3" if len(parts) > 5 and parts[5].strip() else "Open"
                                curNet.privacy = curNet.security
                                curNet.beaconCount = 1 if is_beacon else 0
                                curNet.firstSeen = now
                                curNet.lastSeen = now
                                allNetworks[key] = curNet
                except Exception:
                    pass

        return 0, "", allNetworks

    def scanForNetworks(interfaceName, frequency=0, printResults=False):
        WirelessEngine.ensureInterfaceUp(interfaceName)

        # 1. Monitor mode interface
        if WirelessEngine.isMonitorMode(interfaceName):
            return WirelessEngine.scanMonitorNetworks(interfaceName, frequency, printResults)

        # 2. Managed mode scan via iw
        retCode = -1
        wirelessResult = ""
        try:
            if frequency == 0:
                result = subprocess.run(['iw', 'dev', interfaceName, 'scan'],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=8)
            else:
                result = subprocess.run(['iw', 'dev', interfaceName, 'scan', 'freq', str(frequency)],
                                        stdout=subprocess.PIPE, stderr=subprocess.STDOUT, timeout=8)

            retCode = result.returncode
            wirelessResult = result.stdout.decode('UTF-8', errors='ignore')
        except Exception:
            retCode = -1

        if retCode == 0:
            wirelessNetworks = WirelessEngine.parseIWoutput(wirelessResult)
            return 0, "", wirelessNetworks

        # 3. Resilient fallback to nmcli if unprivileged or interface busy
        nmcli_nets = WirelessEngine.scanViaNmcli(interfaceName, frequency)
        if nmcli_nets and len(nmcli_nets) > 0:
            return 0, "", nmcli_nets

        errString = wirelessResult.replace("\n", " ").strip()
        if retCode == WirelessNetwork.ERR_NETDOWN:
            errString = f"Interface {interfaceName} appears down"
        elif retCode == WirelessNetwork.ERR_DEVICEBUSY:
            errString = f"Interface {interfaceName} is busy"
        elif retCode == WirelessNetwork.ERR_OPNOTPERMITTED:
            errString = f"Root privileges required for iw scan on {interfaceName}."

        return retCode, errString, {}
        
    def getFieldValue(p, curLine):
        matchobj = p.search(curLine)
        
        if not matchobj:
            return ""
            
        try:
            retVal = matchobj.group(1)
        except:
            retVal = ""
            
        return retVal
        
    def parseIWoutput(iwOutput):
        
        # start (regex patterns are module-level constants _P_BSS, _P_SSID, etc.)
        p_bss = _P_BSS
        p_ssid = _P_SSID
        p_ess = _P_ESS
        p_ess_privacy = _P_ESS_PRIVACY
        p_ibss = _P_IBSS
        p_ibss_privacy = _P_IBSS_PRIVACY
        p_auth_suites = _P_AUTH_SUITES
        p_pw_ciphers = _P_PW_CIPHERS
        p_param_channel = _P_PARAM_CHANNEL
        p_primary_channel = _P_PRIMARY_CHANNEL
        p_freq = _P_FREQ
        p_signal = _P_SIGNAL
        p_ht = _P_HT
        p_bw = _P_BW
        p_secondary = _P_SECONDARY
        p_thirdfreq = _P_THIRDFREQ
        p_stationcount = _P_STATIONCOUNT
        p_utilization = _P_UTILIZATION
        retVal = {}
        curNetwork = None
        now=datetime.datetime.now()
        
        # This now supports direct from STDOUT via scanForNetworks,
        # and input from a file as f.readlines() which returns a list
        if type(iwOutput) == str:
            inputLines = iwOutput.splitlines()
        else:
            inputLines = iwOutput
            
        for curLine in inputLines:
            fieldValue = WirelessEngine.getFieldValue(p_bss, curLine)
                
            if (len(fieldValue) > 0):
                # New object
                if curNetwork is not None:
                    # Store first
                    if curNetwork.channel > 0:
                        # I did see incomplete output from iw where not all the data was there
                        retVal[curNetwork.getKey()] = curNetwork

                # Create a new network.  BSSID will be the header for each network
                curNetwork = WirelessNetwork()
                curNetwork.lastSeen = now
                curNetwork.firstSeen = now
                curNetwork.macAddr = fieldValue.upper()
                continue
            
            if curNetwork is None:
                # If we don't have a network object yet, then we haven't
                # seen a BSSID so just keep going through the lines.
                continue

            fieldValue = WirelessEngine.getFieldValue(p_ssid, curLine)
                
            if (len(fieldValue) > 0):
                curNetwork.ssid = WirelessEngine.convertUnknownToString(fieldValue)
                
            fieldValue = WirelessEngine.getFieldValue(p_ess, curLine)
                
            if (len(fieldValue) > 0):
                curNetwork.mode = "AP"
                # Had issue with WEP not showing up.
                # If capability has "ESS Privacy" there's something there.
                # If it's PSK, etc. there will be other RSN fields, etc.
                # So for now start by assuming WEP
                
                # See: https://wiki.archlinux.org/index.php/Wireless_network_configuration
                fieldValue = WirelessEngine.getFieldValue(p_ess_privacy, curLine)
                    
                if (len(fieldValue) > 0):
                    curNetwork.security = "WEP"
                    curNetwork.privacy = "WEP"
                    
                continue #Found the item
                
            fieldValue = WirelessEngine.getFieldValue(p_ibss, curLine)
                
            if (len(fieldValue) > 0):
                curNetwork.mode = "Ad Hoc"
                curNetwork.security = "[Ad-Hoc] Open"

                fieldValue = WirelessEngine.getFieldValue(p_ibss_privacy, curLine)
                    
                if (len(fieldValue) > 0):
                    curNetwork.security = "[Ad-Hoc] WEP"
                    curNetwork.privacy = "WEP"
                    
                continue #Found the item

            # Station count
            fieldValue = WirelessEngine.getFieldValue(p_stationcount, curLine)
            if (len(fieldValue) > 0):
                curNetwork.stationcount = int(fieldValue)
                continue #Found the item
                
            # Utilization
            fieldValue = WirelessEngine.getFieldValue(p_utilization, curLine)
            if (len(fieldValue) > 0):
                utilization = round(float(fieldValue)  / 255.0 * 100.0 * 100.0) / 100.0
                curNetwork.utilization = utilization
                continue #Found the item
                
            # Auth suites
            fieldValue = WirelessEngine.getFieldValue(p_auth_suites, curLine)
                
            if (len(fieldValue) > 0):
                curNetwork.security = fieldValue
                continue #Found the item
                
            # p = re.compile('.*?Group cipher: *(.*)')
            fieldValue = WirelessEngine.getFieldValue(p_pw_ciphers, curLine)
            fieldValue = fieldValue.replace(' ', '/')
                
            if (len(fieldValue) > 0):
                curNetwork.privacy = fieldValue
                curNetwork.cipher = fieldValue
                continue #Found the item
                
            fieldValue = WirelessEngine.getFieldValue(p_param_channel, curLine)
                
            if (len(fieldValue) > 0):
                curNetwork.channel = int(fieldValue)
                continue #Found the item
                
            fieldValue = WirelessEngine.getFieldValue(p_primary_channel, curLine)
                
            if (len(fieldValue) > 0):
                curNetwork.channel = int(fieldValue)
                continue #Found the item
                
            fieldValue = WirelessEngine.getFieldValue(p_freq, curLine)
                
            if (len(fieldValue) > 0):
                curNetwork.frequency = int(fieldValue)
                continue #Found the item
                
            fieldValue = WirelessEngine.getFieldValue(p_signal, curLine)
                
            # This test is different.  dBm is negative so can't test > 0.  10dBm is really high so lets use that
            if (len(fieldValue) > 0):
                curNetwork.signal = int(fieldValue)
                curNetwork.strongestsignal = curNetwork.signal
                continue #Found the item
                
            fieldValue = WirelessEngine.getFieldValue(p_ht, curLine)
                
            if (len(fieldValue) > 0):
                if (curNetwork.bandwidth == 20):
                    curNetwork.bandwidth = 40
                continue #Found the item
                
            fieldValue = WirelessEngine.getFieldValue(p_bw, curLine)
                
            if (len(fieldValue) > 0):
                curNetwork.bandwidth = int(fieldValue)
                continue #Found the item
                
            fieldValue = WirelessEngine.getFieldValue(p_secondary, curLine)
                
            if (len(fieldValue) > 0):
                curNetwork.secondaryChannelLocation = fieldValue
                if (fieldValue == 'above'):
                    curNetwork.secondaryChannel = curNetwork.channel + 4
                elif (fieldValue == 'below'):
                    curNetwork.secondaryChannel = curNetwork.channel - 4
                # else it'll say 'no secondary'
                    
                continue #Found the item
                
            fieldValue = WirelessEngine.getFieldValue(p_thirdfreq, curLine)
                
            if (len(fieldValue) > 0):
                curNetwork.thirdChannel = int(fieldValue)
                    
                continue #Found the item
                
        # #### End loop ######
        
        # Add the last network
        if curNetwork is not None:
            if curNetwork.channel > 0:
                # I did see incomplete output from iw where not all the data was there
                retVal[curNetwork.getKey()] = curNetwork
        
        return retVal
        
if __name__ == '__main__':
    # WirelessEngine.getMacAddress('wlan0mon')
    if os.geteuid() != 0:
        print("ERROR: You need to have root privileges to run this script.  Please try again, this time using 'sudo'. Exiting.\n")
        exit(2)
    # for debugging
    
    # change this interface name to test it.
    wirelessInterfaces = WirelessEngine.getInterfaces()
    
    if len(wirelessInterfaces) == 0:
        print("ERROR: Unable to find wireless interface.\n")
        exit(1)
        
    winterface = wirelessInterfaces[0]
    print('Scanning for wireless networks on ' + winterface + '...')
    
    # Testing to/from Json
    # convert to Json
    retCode, errString, jsonstr=WirelessEngine.getNetworksAsJson(winterface, None)
    # Convert back
    j=json.loads(jsonstr)
    
    # print results
    print('Error Code: ' + str(j['errCode']) + '\n')
    
    if j['errCode'] == 0:
        for curNetDict in j['networks']:
            newNet = WirelessNetwork.createFromJsonDict(curNetDict)
            print(newNet)
            
    else:    
        print('Error String: ' + j['errString'] + '\n')
    
    print('Done.\n')
