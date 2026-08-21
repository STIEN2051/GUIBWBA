#!/usr/bin/env python3
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

import sys
import csv
import os
import subprocess
import re
import json
import datetime
from dateutil import parser
from time import sleep
from threading import Lock

from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QDesktopWidget, QWidget, QTabWidget,
    QVBoxLayout, QHBoxLayout, QMessageBox, QFileDialog,
    QLineEdit, QAbstractItemView, QMenu, QAction,
    QComboBox, QLabel, QPushButton, QCheckBox, QTableWidget,
    QTableWidgetItem, QHeaderView
)
from PyQt5.QtGui import QIcon, QFont, QBrush, QColor
from PyQt5.QtCore import Qt, QTimer
from PyQt5 import QtCore

from wirelessengine import WirelessEngine, WirelessNetwork
from sparrowcommon import BaseThreadClass, stringtobool
from sparrowtablewidgets import IntTableWidgetItem, DateTableWidgetItem, FloatTableWidgetItem
from sparrowbluetooth import SparrowBluetooth, BluetoothDevice

hasOUILookup = False
try:
    from manuf import manuf
    hasOUILookup = True
except Exception:
    hasOUILookup = False


# ------------------ OUI DB Lookup -----------------------
def getOUIDB():
    ouidb = None
    if hasOUILookup:
        updateflag = False
        if os.path.isfile('manuf'):
            last_modified_date = datetime.datetime.fromtimestamp(os.path.getmtime('manuf'))
            now = datetime.datetime.now()
            if (now - last_modified_date).days > 90:
                updateflag = True
        else:
            updateflag = True

        manuf.MacParser.MANUF_URL = "https://www.wireshark.org/download/automated/data/manuf"
        manuf.MacParser.WFA_URL = "https://raw.githubusercontent.com/wireshark/wireshark/master/wka"
        try:
            if updateflag:
                ouidb = manuf.MacParser(manuf_name='manuf', update=True)
            else:
                ouidb = manuf.MacParser(manuf_name='manuf', update=False)
        except Exception:
            try:
                ouidb = manuf.MacParser(update=False)
            except Exception:
                ouidb = None
    return ouidb


# ------------------ Local WiFi Scan Thread ------------------------------
class ScanThread(BaseThreadClass):
    def __init__(self, interface, mainWin, channelList=None):
        super().__init__()
        self.interface = interface
        self.mainWin = mainWin
        self.scanDelay = 0.5  # seconds
        self.channelList = channelList

    def run(self):
        self.threadRunning = True

        while not self.signalStop:
            if (self.channelList is None) or (len(self.channelList) == 0):
                # All-channel / Normal mode
                retCode, errString, wirelessNetworks = WirelessEngine.scanForNetworks(self.interface)
                if retCode == 0:
                    if wirelessNetworks and (len(wirelessNetworks) > 0) and (not self.signalStop):
                        if not self.mainWin._tableUpdateInProgress:
                            self.mainWin.scanresults.emit(wirelessNetworks)
                else:
                    if retCode != WirelessNetwork.ERR_DEVICEBUSY:
                        self.mainWin.errmsg.emit(retCode, errString)

                sleep(self.scanDelay)
            else:
                # Channel hunt mode
                for curFrequency in self.channelList:
                    if self.signalStop:
                        break
                    retCode, errString, wirelessNetworks = WirelessEngine.scanForNetworks(self.interface, curFrequency)
                    if retCode == 0:
                        if wirelessNetworks and (len(wirelessNetworks) > 0) and (not self.signalStop):
                            if not self.mainWin._tableUpdateInProgress:
                                self.mainWin.scanresults.emit(wirelessNetworks)
                    else:
                        if retCode != WirelessNetwork.ERR_DEVICEBUSY:
                            self.mainWin.errmsg.emit(retCode, errString)

                    sleep(self.scanDelay)

        self.threadRunning = False


# ------------------ Main Application Window ------------------------------
class mainWindow(QMainWindow):

    # Signals
    scanresults = QtCore.pyqtSignal(dict)
    errmsg = QtCore.pyqtSignal(int, str)
    rescanInterfaces = QtCore.pyqtSignal()

    def __init__(self):
        super().__init__()

        self.rescanInterfaces.connect(self.onRescanInterfaces)
        self.scanresults.connect(self.scanResults)
        self.errmsg.connect(self.onErrMsg)

        # OUI database
        self.ouiLookupEngine = getOUIDB()
        self._vendorCache = {}

        # WiFi Scanner State
        self.scanRunning = False
        self.scanThread = None
        self.scanDelay = 0.5
        self.scanMode = "Normal"
        self.huntChannelList = []
        self.updateLock = Lock()
        self._tableUpdateInProgress = False
        self.wifiTableSortOrder = Qt.DescendingOrder
        self.wifiTableSortIndex = -1

        # Bluetooth Scanner State
        self.hasBluetooth = False
        self.hasUbertooth = False
        self.bluetooth = None
        self.btUpdateLock = Lock()
        self.btTableSortOrder = Qt.DescendingOrder
        self.btTableSortIndex = -1
        self.checkForBluetooth()

        self.btTimer = QTimer()
        self.btTimer.timeout.connect(self.onBtTimer)
        self.btTimer.setSingleShot(True)
        self.btTimerTimeout = 500

        # Check root privileges (Linux only)
        if hasattr(os, 'geteuid') and os.geteuid() != 0:
            self.runningAsRoot = False
        else:
            self.runningAsRoot = True

        self.initUI()

    def checkForBluetooth(self):
        self.hasBluetooth = False
        self.hasUbertooth = False

        try:
            numBtAdapters = len(SparrowBluetooth.getBluetoothInterfaces())
            if numBtAdapters > 0:
                self.hasBluetooth = True
        except Exception:
            self.hasBluetooth = False

        try:
            if SparrowBluetooth.getNumUbertoothDevices() > 0:
                errcode, errmsg = SparrowBluetooth.hasUbertoothTools()
                if errcode == 0:
                    self.hasUbertooth = True
        except Exception:
            self.hasUbertooth = False

        if self.hasBluetooth or self.hasUbertooth:
            try:
                self.bluetooth = SparrowBluetooth()
            except Exception:
                self.bluetooth = None
        else:
            self.bluetooth = None

    def ouiLookup(self, macAddr):
        if not macAddr:
            return ""
        if macAddr in self._vendorCache:
            return self._vendorCache[macAddr]

        clientVendor = ""
        if hasOUILookup and self.ouiLookupEngine:
            try:
                clientVendor = self.ouiLookupEngine.get_manuf(macAddr)
                if clientVendor is None:
                    clientVendor = ""
            except Exception:
                clientVendor = ""

        self._vendorCache[macAddr] = clientVendor
        return clientVendor

    def initUI(self):
        desktopSize = QApplication.desktop().screenGeometry()
        mainWidth = min(max(1050, desktopSize.width() * 3 // 4), 1600)
        mainHeight = min(max(650, desktopSize.height() * 3 // 4), 1000)
        self.resize(mainWidth, mainHeight)
        self.center()
        self.setWindowTitle('Sparrow - WiFi & Bluetooth Scanner')
        if os.path.isfile('wifi_icon.png'):
            self.setWindowIcon(QIcon('wifi_icon.png'))

        self.createMenu()

        # Central Tab Widget
        self.tabs = QTabWidget(self)
        self.setCentralWidget(self.tabs)

        self.wifiTab = self.createWifiTab()
        self.btTab = self.createBluetoothTab()

        self.tabs.addTab(self.wifiTab, "  \u25A0  WiFi Scanner  ")
        self.tabs.addTab(self.btTab, "  \u25A0  Bluetooth Scanner  ")

        # Status Bar
        self.statusBar().setStyleSheet("QStatusBar{background:rgba(220,220,220,255);color:black;border-top: 1px solid #999;}")
        if not self.runningAsRoot:
            self.statusBar().showMessage('Note: Root privileges may be required for active packet injection or raw monitor scans.')
        else:
            self.statusBar().showMessage('Ready.')

        self.setBlackoutColors()
        self.show()

    def createMenu(self):
        menubar = self.menuBar()

        # File Menu
        fileMenu = menubar.addMenu('&File')

        clearAct = QAction('&Clear All Data', self)
        clearAct.setShortcut('Ctrl+N')
        clearAct.setStatusTip('Clear WiFi and Bluetooth scanner tables')
        clearAct.triggered.connect(self.onClearAllData)
        fileMenu.addAction(clearAct)

        fileMenu.addSeparator()

        importMenu = fileMenu.addMenu('&Import WiFi Scan')
        impCsvAct = QAction('From &CSV', self)
        impCsvAct.setStatusTip('Import WiFi scan from CSV')
        impCsvAct.triggered.connect(self.onImportCSV)
        importMenu.addAction(impCsvAct)

        impJsonAct = QAction('From &JSON', self)
        impJsonAct.setStatusTip('Import WiFi scan from JSON')
        impJsonAct.triggered.connect(self.onImportJSON)
        importMenu.addAction(impJsonAct)

        importMenu.addSeparator()
        impIwAct = QAction('From &iw scan output', self)
        impIwAct.setStatusTip("Import raw 'iw dev <interface> scan' output")
        impIwAct.triggered.connect(self.onImportIWData)
        importMenu.addAction(impIwAct)

        exportMenu = fileMenu.addMenu('&Export Scan')
        expWifiCsvAct = QAction('WiFi to &CSV', self)
        expWifiCsvAct.setStatusTip('Export WiFi scan to CSV')
        expWifiCsvAct.triggered.connect(self.onExportCSV)
        exportMenu.addAction(expWifiCsvAct)

        expWifiJsonAct = QAction('WiFi to &JSON', self)
        expWifiJsonAct.setStatusTip('Export WiFi scan to JSON')
        expWifiJsonAct.triggered.connect(self.onExportJSON)
        exportMenu.addAction(expWifiJsonAct)

        exportMenu.addSeparator()
        expBtCsvAct = QAction('Bluetooth to C&SV', self)
        expBtCsvAct.setStatusTip('Export Bluetooth scan to CSV')
        expBtCsvAct.triggered.connect(self.onExportBtCSV)
        exportMenu.addAction(expBtCsvAct)

        fileMenu.addSeparator()
        exitAct = QAction('&Exit', self)
        exitAct.setShortcut('Ctrl+X')
        exitAct.setStatusTip('Exit application')
        exitAct.triggered.connect(self.close)
        fileMenu.addAction(exitAct)

        # Help Menu
        helpMenu = menubar.addMenu('&Help')
        aboutAct = QAction('&About', self)
        aboutAct.setStatusTip('About Sparrow Scanner')
        aboutAct.triggered.connect(self.onAbout)
        helpMenu.addAction(aboutAct)

    # ------------------ WiFi Tab Construction ------------------
    def createWifiTab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Top Controls Bar
        controlsLayout = QHBoxLayout()
        controlsLayout.setSpacing(10)

        # Interface label & dropdown
        lblInterface = QLabel("Local Interface:", tab)
        lblInterface.setStyleSheet("font-weight: bold;")
        controlsLayout.addWidget(lblInterface)

        self.combo = QComboBox(tab)
        self.combo.setMinimumWidth(120)
        interfaces = WirelessEngine.getInterfaces()
        if len(interfaces) > 0:
            for curInterface in interfaces:
                self.combo.addItem(curInterface)
        else:
            self.combo.addItem("No interfaces found")
            self.combo.setEnabled(False)
        controlsLayout.addWidget(self.combo)

        # Rescan interfaces button
        self.btnRefreshIface = QPushButton("Rescan", tab)
        self.btnRefreshIface.setToolTip("Refresh wireless network interfaces list")
        self.btnRefreshIface.clicked.connect(self.onRescanInterfaces)
        controlsLayout.addWidget(self.btnRefreshIface)

        # Scan Button
        self.btnScan = QPushButton("&Scan", tab)
        self.btnScan.setCheckable(True)
        self.btnScan.setShortcut('Ctrl+S')
        self.btnScan.setMinimumWidth(90)
        self.btnScan.setStyleSheet("background-color: rgba(0,128,192,255); color: white; font-weight: bold; border-radius: 3px; padding: 5px 12px;")
        self.btnScan.clicked[bool].connect(self.onScanClicked)
        controlsLayout.addWidget(self.btnScan)

        # Scan Mode selector
        lblScanMode = QLabel("Mode:", tab)
        lblScanMode.setStyleSheet("font-weight: bold;")
        controlsLayout.addWidget(lblScanMode)

        self.scanModeCombo = QComboBox(tab)
        self.scanModeCombo.setStatusTip('All-channel normal scans take 5-10s. Use Hunt mode for single channel/freq.')
        self.scanModeCombo.addItem("Normal")
        self.scanModeCombo.addItem("Hunt")
        self.scanModeCombo.currentIndexChanged.connect(self.onScanModeChanged)
        controlsLayout.addWidget(self.scanModeCombo)

        # Hunt channels input
        self.lblHuntChannels = QLabel("Hunt Channels/Freqs:", tab)
        self.lblHuntChannels.setVisible(False)
        controlsLayout.addWidget(self.lblHuntChannels)

        self.huntChannels = QLineEdit(tab)
        self.huntChannels.setStatusTip('Specify comma-separated channels (e.g., 1,6,11) or frequencies.')
        self.huntChannels.setMaximumWidth(120)
        self.huntChannels.setText('1')
        self.huntChannels.setVisible(False)
        controlsLayout.addWidget(self.huntChannels)

        # Age out checkbox
        self.cbAgeOut = QCheckBox("Auto-remove inactive (> 3 min)", tab)
        self.cbAgeOut.setChecked(False)
        controlsLayout.addWidget(self.cbAgeOut)

        controlsLayout.addStretch()

        # Clear button
        self.btnClearWifi = QPushButton("Clear", tab)
        self.btnClearWifi.clicked.connect(self.onClearWifiData)
        controlsLayout.addWidget(self.btnClearWifi)

        # Export CSV button
        self.btnExportWifi = QPushButton("Export CSV", tab)
        self.btnExportWifi.clicked.connect(self.onExportCSV)
        controlsLayout.addWidget(self.btnExportWifi)

        layout.addLayout(controlsLayout)

        # Network Table
        self.networkTable = QTableWidget(tab)
        self.networkTable.setColumnCount(13)
        self.networkTable.setShowGrid(True)
        self.networkTable.setHorizontalHeaderLabels([
            'MAC Address', 'Vendor', 'SSID', 'Security', 'Privacy',
            'Channel', 'Frequency (MHz)', 'Signal (dBm)', 'Bandwidth (MHz)',
            '% Utilization', 'Stations', 'Last Seen', 'First Seen'
        ])
        self.networkTable.setRowCount(0)
        self.networkTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.networkTable.horizontalHeader().sectionClicked.connect(self.onWifiTableHeadingClicked)
        self.networkTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.networkTable.setSelectionBehavior(QAbstractItemView.SelectRows)

        # Right-click context menu
        self.networkTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.networkTable.customContextMenuRequested.connect(self.showWifiTableContextMenu)

        self.wifiContextMenu = QMenu(tab)
        copyAct = QAction('Copy Cell', tab)
        copyAct.triggered.connect(self.onCopyWifiCell)
        self.wifiContextMenu.addAction(copyAct)

        self.wifiContextMenu.addSeparator()

        deleteAct = QAction('Delete Selected Network', tab)
        deleteAct.triggered.connect(self.onDeleteWifiNet)
        self.wifiContextMenu.addAction(deleteAct)

        layout.addWidget(self.networkTable)
        return tab

    # ------------------ Bluetooth Tab Construction ------------------
    def createBluetoothTab(self):
        tab = QWidget()
        layout = QVBoxLayout(tab)
        layout.setContentsMargins(10, 10, 10, 10)
        layout.setSpacing(8)

        # Top Controls Bar
        controlsLayout = QHBoxLayout()
        controlsLayout.setSpacing(10)

        # Scan Type label & combo
        lblBtType = QLabel("Scan Type:", tab)
        lblBtType.setStyleSheet("font-weight: bold;")
        controlsLayout.addWidget(lblBtType)

        self.comboBtScanType = QComboBox(tab)
        self.comboBtScanType.setMinimumWidth(210)
        if self.hasUbertooth:
            self.comboBtScanType.addItem('Promiscuous Discovery (Ubertooth)')
        self.comboBtScanType.addItem('LE Advertisement Discovery')
        controlsLayout.addWidget(self.comboBtScanType)

        # Scan Button
        self.btnBtScan = QPushButton("&Scan", tab)
        self.btnBtScan.setCheckable(True)
        self.btnBtScan.setShortcut('Ctrl+B')
        self.btnBtScan.setMinimumWidth(90)
        self.btnBtScan.setStyleSheet("background-color: rgba(0,128,192,255); color: white; font-weight: bold; border-radius: 3px; padding: 5px 12px;")
        self.btnBtScan.clicked[bool].connect(self.onBtScanClicked)
        controlsLayout.addWidget(self.btnBtScan)

        if not self.hasBluetooth and not self.hasUbertooth:
            lblNoBt = QLabel("(No Bluetooth / Ubertooth adapter detected)", tab)
            lblNoBt.setStyleSheet("color: #888; font-style: italic;")
            controlsLayout.addWidget(lblNoBt)

        controlsLayout.addStretch()

        # Clear button
        self.btnClearBt = QPushButton("Clear", tab)
        self.btnClearBt.clicked.connect(self.onClearBtData)
        controlsLayout.addWidget(self.btnClearBt)

        # Export button
        self.btnExportBt = QPushButton("Export CSV", tab)
        self.btnExportBt.clicked.connect(self.onExportBtCSV)
        controlsLayout.addWidget(self.btnExportBt)

        layout.addLayout(controlsLayout)

        # Bluetooth Table
        self.bluetoothTable = QTableWidget(tab)
        self.bluetoothTable.setColumnCount(10)
        self.bluetoothTable.setShowGrid(True)
        self.bluetoothTable.setHorizontalHeaderLabels([
            'UUID', 'Address (MAC)', 'Name', 'Company', 'Manufacturer',
            'Type', 'RSSI (dBm)', 'TX Power', 'Est Range (m)', 'Last Seen'
        ])
        self.bluetoothTable.setRowCount(0)
        self.bluetoothTable.horizontalHeader().setSectionResizeMode(2, QHeaderView.Stretch)
        self.bluetoothTable.horizontalHeader().sectionClicked.connect(self.onBtTableHeadingClicked)
        self.bluetoothTable.setSelectionMode(QAbstractItemView.SingleSelection)
        self.bluetoothTable.setSelectionBehavior(QAbstractItemView.SelectRows)

        # Right-click context menu
        self.bluetoothTable.setContextMenuPolicy(Qt.CustomContextMenu)
        self.bluetoothTable.customContextMenuRequested.connect(self.showBtTableContextMenu)

        self.btContextMenu = QMenu(tab)
        copyBtAct = QAction('Copy Cell', tab)
        copyBtAct.triggered.connect(self.onCopyBtCell)
        self.btContextMenu.addAction(copyBtAct)

        layout.addWidget(self.bluetoothTable)
        return tab

    # ------------------ UI Styling ------------------
    def setBlackoutColors(self):
        tableStyle = (
            "QTableView {"
            "  background-color: #121212;"
            "  gridline-color: #333333;"
            "  color: #E0E0E0;"
            "  selection-background-color: #005080;"
            "  selection-color: #FFFFFF;"
            "}"
            "QTableCornerButton::section { background-color: #222222; border: 1px solid #333; }"
        )
        headerStyle = (
            "QHeaderView::section {"
            "  background-color: #222222;"
            "  border: 1px solid #444444;"
            "  color: #EEEEEE;"
            "  padding: 4px 6px;"
            "  font-weight: bold;"
            "}"
            "QHeaderView::down-arrow, QHeaderView::up-arrow { background: none; }"
        )

        self.networkTable.setStyleSheet(tableStyle)
        self.networkTable.horizontalHeader().setStyleSheet(headerStyle)
        self.networkTable.verticalHeader().setStyleSheet(headerStyle)

        self.bluetoothTable.setStyleSheet(tableStyle)
        self.bluetoothTable.horizontalHeader().setStyleSheet(headerStyle)
        self.bluetoothTable.verticalHeader().setStyleSheet(headerStyle)

        tabStyle = (
            "QTabWidget::pane { border: 1px solid #444; background: #1a1a1a; }"
            "QTabBar::tab {"
            "  background: #2b2b2b; color: #bbb; padding: 8px 18px; border: 1px solid #444; border-bottom: none; font-weight: bold; border-top-left-radius: 4px; border-top-right-radius: 4px;"
            "}"
            "QTabBar::tab:selected { background: #0080c0; color: white; }"
            "QTabBar::tab:hover:!selected { background: #3a3a3a; color: white; }"
        )
        self.tabs.setStyleSheet(tabStyle)

    def center(self):
        qr = self.frameGeometry()
        cp = QDesktopWidget().availableGeometry().center()
        qr.moveCenter(cp)
        self.move(qr.topLeft())

    # ------------------ WiFi Scanning & Table Handlers ------------------
    def onScanModeChanged(self):
        self.scanMode = str(self.scanModeCombo.currentText())
        if self.scanMode == "Normal":
            self.huntChannels.setVisible(False)
            self.lblHuntChannels.setVisible(False)
        else:
            self.huntChannels.setVisible(True)
            self.lblHuntChannels.setVisible(True)
        self.getHuntChannels()

    def getHuntChannels(self):
        self.huntChannelList = []
        channelStr = self.huntChannels.text().replace(' ', '')
        if ',' in channelStr:
            tmpList = channelStr.split(',')
        else:
            tmpList = [channelStr] if channelStr else []

        for curItem in tmpList:
            if len(curItem) > 0:
                try:
                    freqForChannel = WirelessEngine.getFrequencyForChannel(curItem)
                    if freqForChannel is not None:
                        self.huntChannelList.append(int(freqForChannel))
                    else:
                        self.huntChannelList.append(int(curItem))
                except Exception:
                    pass

    def onScanClicked(self, pressed):
        self.scanRunning = pressed

        if not self.scanRunning:
            if self.scanThread:
                self.setCursor(Qt.WaitCursor)
                self.scanThread.signalStop = True
                while self.scanThread.threadRunning:
                    self.statusBar().showMessage('Waiting for active WiFi scan to finish...')
                    QApplication.processEvents()
                    sleep(0.05)
                self.scanThread = None
                self.setCursor(Qt.ArrowCursor)
            self.statusBar().showMessage('WiFi Scanner stopped. Ready.')
        else:
            if self.combo.count() > 0 and self.combo.isEnabled():
                curInterface = str(self.combo.currentText())
                self.statusBar().showMessage(f'Scanning WiFi on interface {curInterface}...')
                if self.scanMode == "Normal" or (len(self.huntChannelList) == 0):
                    self.scanThread = ScanThread(curInterface, self)
                else:
                    self.getHuntChannels()
                    self.scanThread = ScanThread(curInterface, self, self.huntChannelList)
                self.scanThread.scanDelay = self.scanDelay
                self.scanThread.start()
            else:
                QMessageBox.question(self, 'Error', "No wireless adapters available.", QMessageBox.Ok)
                self.scanRunning = False
                self.btnScan.setChecked(False)

        if self.btnScan.isChecked():
            self.btnScan.setStyleSheet("background-color: rgba(220,0,0,255); color: white; font-weight: bold; border-radius: 3px; padding: 5px 12px;")
            self.btnScan.setText('&Stop')
            self.scanModeCombo.setEnabled(False)
            self.huntChannels.setEnabled(False)
            self.combo.setEnabled(False)
            self.btnRefreshIface.setEnabled(False)
        else:
            self.btnScan.setStyleSheet("background-color: rgba(0,128,192,255); color: white; font-weight: bold; border-radius: 3px; padding: 5px 12px;")
            self.btnScan.setText('&Scan')
            self.scanModeCombo.setEnabled(True)
            self.huntChannels.setEnabled(True)
            self.combo.setEnabled(True)
            self.btnRefreshIface.setEnabled(True)

        self.btnScan.setShortcut('Ctrl+S')

    def scanResults(self, wirelessNetworks):
        if self.scanRunning:
            self.populateTable(wirelessNetworks)

    def onErrMsg(self, errCode, errMsg):
        self.statusBar().showMessage(f"Error [{errCode}]: {errMsg}")
        if errCode in (WirelessNetwork.ERR_NETDOWN, WirelessNetwork.ERR_OPNOTSUPPORTED, WirelessNetwork.ERR_OPNOTPERMITTED):
            if self.scanThread:
                self.scanThread.signalStop = True
                while self.scanThread is not None and self.scanThread.threadRunning:
                    QApplication.processEvents()
                    sleep(0.05)
                self.scanThread = None
                self.scanRunning = False
                self.btnScan.setChecked(False)
                self.btnScan.setStyleSheet("background-color: rgba(0,128,192,255); color: white; font-weight: bold; border-radius: 3px; padding: 5px 12px;")
                self.btnScan.setText('&Scan')
                self.scanModeCombo.setEnabled(True)
                self.huntChannels.setEnabled(True)
                self.combo.setEnabled(True)
                self.btnRefreshIface.setEnabled(True)

    def populateUpdateExisting(self, wirelessNetworks):
        numRows = self.networkTable.rowCount()
        if numRows <= 0:
            return

        networkLookup = {net.getKey(): net for net in wirelessNetworks.values()}
        for curRow in range(0, numRows):
            try:
                curData = self.networkTable.item(curRow, 2).data(Qt.UserRole + 1)
            except Exception:
                curData = None

            if curData:
                curNet = networkLookup.get(curData.getKey())
                if curNet:
                    clientVendor = self.ouiLookup(curNet.macAddr)
                    self.networkTable.item(curRow, 1).setText(clientVendor)
                    self.networkTable.item(curRow, 3).setText(curNet.security)
                    self.networkTable.item(curRow, 4).setText(curNet.privacy)
                    self.networkTable.item(curRow, 5).setText(str(curNet.getChannelString()))
                    self.networkTable.item(curRow, 6).setText(str(curNet.frequency))
                    self.networkTable.item(curRow, 7).setText(str(curNet.signal))
                    self.networkTable.item(curRow, 8).setText(str(curNet.bandwidth))
                    self.networkTable.item(curRow, 9).setText(str(curNet.utilization))
                    self.networkTable.item(curRow, 10).setText(str(curNet.stationcount))
                    self.networkTable.item(curRow, 11).setText(curNet.lastSeen.strftime("%m/%d/%Y %H:%M:%S"))

                    curNet.firstSeen = curData.firstSeen
                    self.networkTable.item(curRow, 12).setText(curNet.firstSeen.strftime("%m/%d/%Y %H:%M:%S"))

                    curNet.foundInList = True
                    self.networkTable.item(curRow, 2).setData(Qt.UserRole + 1, curNet)

    def populateTable(self, wirelessNetworks):
        self._tableUpdateInProgress = True
        self.updateLock.acquire()

        try:
            self.populateUpdateExisting(wirelessNetworks)

            addedNetworks = 0
            firstTableLoad = False

            for curKey in wirelessNetworks.keys():
                curNet = wirelessNetworks[curKey]
                if curNet.foundInList:
                    continue

                addedNetworks += 1
                rowPosition = self.networkTable.rowCount()
                if rowPosition == 0:
                    firstTableLoad = True

                self.networkTable.insertRow(0)

                # Column 0: MAC
                self.networkTable.setItem(0, 0, QTableWidgetItem(curNet.macAddr))

                # Column 1: Vendor
                clientVendor = self.ouiLookup(curNet.macAddr)
                self.networkTable.setItem(0, 1, QTableWidgetItem(clientVendor))

                # Column 2: SSID
                tmpssid = curNet.ssid if curNet.ssid else '<Unknown>'
                ssidItem = QTableWidgetItem(tmpssid)
                ssidItem.setData(Qt.UserRole + 1, curNet)
                self.networkTable.setItem(0, 2, ssidItem)

                # Columns 3-12: Properties
                self.networkTable.setItem(0, 3, QTableWidgetItem(curNet.security))
                self.networkTable.setItem(0, 4, QTableWidgetItem(curNet.privacy))
                self.networkTable.setItem(0, 5, IntTableWidgetItem(str(curNet.getChannelString())))
                self.networkTable.setItem(0, 6, IntTableWidgetItem(str(curNet.frequency)))
                self.networkTable.setItem(0, 7, IntTableWidgetItem(str(curNet.signal)))
                self.networkTable.setItem(0, 8, IntTableWidgetItem(str(curNet.bandwidth)))
                self.networkTable.setItem(0, 9, FloatTableWidgetItem(str(curNet.utilization)))
                self.networkTable.setItem(0, 10, IntTableWidgetItem(str(curNet.stationcount)))
                self.networkTable.setItem(0, 11, DateTableWidgetItem(curNet.lastSeen.strftime("%m/%d/%Y %H:%M:%S")))
                self.networkTable.setItem(0, 12, DateTableWidgetItem(curNet.firstSeen.strftime("%m/%d/%Y %H:%M:%S")))

            self.ageOut()

            if firstTableLoad:
                self.networkTable.resizeColumnsToContents()

            if addedNetworks > 0 and self.wifiTableSortIndex >= 0:
                self.networkTable.sortItems(self.wifiTableSortIndex, self.wifiTableSortOrder)

        finally:
            self.updateLock.release()
            self._tableUpdateInProgress = False

    def ageOut(self):
        numRows = self.networkTable.rowCount()
        if self.cbAgeOut.isChecked() and numRows > 0:
            maxTime = datetime.datetime.now() - datetime.timedelta(minutes=3)
            for i in range(numRows - 1, -1, -1):
                try:
                    curData = self.networkTable.item(i, 2).data(Qt.UserRole + 1)
                    if curData.lastSeen < maxTime:
                        self.networkTable.removeRow(i)
                except Exception:
                    self.networkTable.removeRow(i)

    def onWifiTableHeadingClicked(self, logical_index):
        header = self.networkTable.horizontalHeader()
        order = Qt.DescendingOrder
        if not header.isSortIndicatorShown():
            header.setSortIndicatorShown(True)
        elif header.sortIndicatorSection() == logical_index:
            order = header.sortIndicatorOrder()
        header.setSortIndicator(logical_index, order)

        self.wifiTableSortOrder = order
        self.wifiTableSortIndex = logical_index
        self.networkTable.sortItems(logical_index, order)

    def showWifiTableContextMenu(self, pos):
        if self.networkTable.currentRow() != -1:
            self.wifiContextMenu.exec_(self.networkTable.mapToGlobal(pos))

    def onCopyWifiCell(self):
        row = self.networkTable.currentRow()
        col = self.networkTable.currentColumn()
        if row >= 0 and col >= 0:
            item = self.networkTable.item(row, col)
            if item:
                QApplication.clipboard().setText(item.text())

    def onDeleteWifiNet(self):
        self.updateLock.acquire()
        try:
            row = self.networkTable.currentRow()
            if row >= 0:
                self.networkTable.removeRow(row)
        finally:
            self.updateLock.release()

    def onClearWifiData(self):
        self.updateLock.acquire()
        try:
            self.networkTable.setRowCount(0)
        finally:
            self.updateLock.release()

    def onRescanInterfaces(self):
        self.combo.clear()
        interfaces = WirelessEngine.getInterfaces()
        if len(interfaces) > 0:
            for curInterface in interfaces:
                self.combo.addItem(curInterface)
            self.combo.setEnabled(True)
            self.statusBar().showMessage(f"Found {len(interfaces)} wireless interface(s).")
        else:
            self.combo.addItem("No interfaces found")
            self.combo.setEnabled(False)
            self.statusBar().showMessage("No wireless interfaces found.")

    # ------------------ Bluetooth Scanning & Table Handlers ------------------
    def onBtScanClicked(self, pressed):
        if not self.bluetooth:
            self.checkForBluetooth()
            if not self.bluetooth:
                QMessageBox.question(self, 'Error', "No Bluetooth interface available.", QMessageBox.Ok)
                self.btnBtScan.setChecked(False)
                return

        if self.btnBtScan.isChecked():
            is_ubertooth = (self.comboBtScanType.currentText().startswith('Promiscuous') and self.hasUbertooth)
            self.btnBtScan.setStyleSheet("background-color: rgba(220,0,0,255); color: white; font-weight: bold; border-radius: 3px; padding: 5px 12px;")
            self.btnBtScan.setText('&Stop')
            self.comboBtScanType.setEnabled(False)

            self.bluetooth.startDiscovery(useBlueHydra=False)
            self.btTimer.start(self.btTimerTimeout)
            self.statusBar().showMessage("Bluetooth discovery active...")
        else:
            self.btTimer.stop()
            self.btnBtScan.setStyleSheet("background-color: rgba(0,128,192,255); color: white; font-weight: bold; border-radius: 3px; padding: 5px 12px;")
            self.btnBtScan.setText('&Scan')
            self.comboBtScanType.setEnabled(True)

            self.setCursor(Qt.WaitCursor)
            if self.bluetooth:
                self.bluetooth.stopDiscovery()
            self.setCursor(Qt.ArrowCursor)
            self.statusBar().showMessage("Bluetooth Scanner stopped. Ready.")

        self.btnBtScan.setShortcut('Ctrl+B')

    def onBtTimer(self):
        if not self.bluetooth:
            return

        try:
            self.bluetooth.updateDeviceList()
            devices = self.bluetooth.devices
        except Exception:
            devices = None

        if devices and len(devices) > 0:
            now = datetime.datetime.now()
            if hasattr(self.bluetooth, 'deviceLock'):
                self.bluetooth.deviceLock.acquire()
            try:
                for curKey in devices.keys():
                    curDevice = devices[curKey]
                    curDevice.manufacturer = self.ouiLookup(curDevice.macAddress)
                self.updateBtTable(devices)
            finally:
                if hasattr(self.bluetooth, 'deviceLock'):
                    self.bluetooth.deviceLock.release()

        if self.btnBtScan.isChecked():
            self.btTimer.start(self.btTimerTimeout)

    def updateBtTable(self, deviceList):
        self.btUpdateLock.acquire()
        try:
            numRows = self.bluetoothTable.rowCount()
            if numRows > 0:
                for curRow in range(0, numRows):
                    try:
                        curData = self.bluetoothTable.item(curRow, 0).data(Qt.UserRole)
                    except Exception:
                        curData = None

                    if curData:
                        for curKey in deviceList.keys():
                            curDevice = deviceList[curKey]
                            if curData.getKey() == curDevice.getKey():
                                curDevice.foundInList = True
                                curDevice.firstSeen = curData.firstSeen

                                self.bluetoothTable.item(curRow, 2).setText(curDevice.name)
                                self.bluetoothTable.item(curRow, 6).setText(str(curDevice.rssi))

                                if curDevice.txPowerValid:
                                    self.bluetoothTable.item(curRow, 7).setText(str(curDevice.txPower))
                                else:
                                    self.bluetoothTable.item(curRow, 7).setText('Unknown')

                                if curDevice.iBeaconRange != -1 and curDevice.txPowerValid:
                                    self.bluetoothTable.item(curRow, 8).setText(str(round(curDevice.iBeaconRange, 2)))
                                else:
                                    self.bluetoothTable.item(curRow, 8).setText('Unknown')

                                self.bluetoothTable.item(curRow, 9).setText(curDevice.lastSeen.strftime("%m/%d/%Y %H:%M:%S"))
                                self.bluetoothTable.item(curRow, 0).setData(Qt.UserRole, curDevice)
                                break

            addedDevices = 0
            for curKey in deviceList.keys():
                curDevice = deviceList[curKey]
                if not curDevice.foundInList:
                    addedDevices += 1
                    self.bluetoothTable.insertRow(0)

                    uuidItem = QTableWidgetItem(curDevice.uuid)
                    uuidItem.setData(Qt.UserRole, curDevice)
                    self.bluetoothTable.setItem(0, 0, uuidItem)
                    self.bluetoothTable.setItem(0, 1, QTableWidgetItem(curDevice.macAddress))
                    self.bluetoothTable.setItem(0, 2, QTableWidgetItem(curDevice.name))
                    self.bluetoothTable.setItem(0, 3, QTableWidgetItem(curDevice.company))
                    self.bluetoothTable.setItem(0, 4, QTableWidgetItem(curDevice.manufacturer))

                    btTypeStr = 'BTLE' if curDevice.btType == BluetoothDevice.BT_LE else 'Classic'
                    self.bluetoothTable.setItem(0, 5, QTableWidgetItem(btTypeStr))
                    self.bluetoothTable.setItem(0, 6, IntTableWidgetItem(str(curDevice.rssi)))

                    if curDevice.txPowerValid:
                        self.bluetoothTable.setItem(0, 7, IntTableWidgetItem(str(curDevice.txPower)))
                    else:
                        self.bluetoothTable.setItem(0, 7, QTableWidgetItem('Unknown'))

                    if curDevice.iBeaconRange != -1 and curDevice.txPowerValid:
                        self.bluetoothTable.setItem(0, 8, FloatTableWidgetItem(str(round(curDevice.iBeaconRange, 2))))
                    else:
                        self.bluetoothTable.setItem(0, 8, QTableWidgetItem('Unknown'))

                    self.bluetoothTable.setItem(0, 9, DateTableWidgetItem(curDevice.lastSeen.strftime("%m/%d/%Y %H:%M:%S")))

            if addedDevices > 0 and self.btTableSortIndex >= 0:
                self.bluetoothTable.sortItems(self.btTableSortIndex, self.btTableSortOrder)

        finally:
            self.btUpdateLock.release()

    def onBtTableHeadingClicked(self, logical_index):
        header = self.bluetoothTable.horizontalHeader()
        order = Qt.DescendingOrder
        if not header.isSortIndicatorShown():
            header.setSortIndicatorShown(True)
        elif header.sortIndicatorSection() == logical_index:
            order = header.sortIndicatorOrder()
        header.setSortIndicator(logical_index, order)

        self.btTableSortOrder = order
        self.btTableSortIndex = logical_index
        self.bluetoothTable.sortItems(logical_index, order)

    def showBtTableContextMenu(self, pos):
        if self.bluetoothTable.currentRow() != -1:
            self.btContextMenu.exec_(self.bluetoothTable.mapToGlobal(pos))

    def onCopyBtCell(self):
        row = self.bluetoothTable.currentRow()
        col = self.bluetoothTable.currentColumn()
        if row >= 0 and col >= 0:
            item = self.bluetoothTable.item(row, col)
            if item:
                QApplication.clipboard().setText(item.text())

    def onClearBtData(self):
        self.btUpdateLock.acquire()
        try:
            self.bluetoothTable.setRowCount(0)
            if self.bluetooth:
                self.bluetooth.devices = {}
        finally:
            self.btUpdateLock.release()

    def onExportBtCSV(self):
        fileName = self.saveFileDialog("CSV Files (*.csv);;All Files (*)")
        if not fileName:
            return

        try:
            outputFile = open(fileName, 'w', newline='', encoding='utf-8')
        except Exception as e:
            QMessageBox.question(self, 'Error', f"Unable to write to {fileName}: {e}", QMessageBox.Ok)
            return

        outputFile.write('UUID,Address,Name,Company,Manufacturer,Type,RSSI,TX Power,Est Range (m),Last Seen\n')
        self.btUpdateLock.acquire()
        try:
            numItems = self.bluetoothTable.rowCount()
            for i in range(0, numItems):
                curData = self.bluetoothTable.item(i, 0).data(Qt.UserRole)
                if curData:
                    btType = "BTLE" if curData.btType == BluetoothDevice.BT_LE else "Classic"
                    txPower = str(curData.txPower) if curData.txPowerValid else 'Unknown'
                    rangeStr = str(curData.iBeaconRange) if curData.iBeaconRange != -1 else 'Unknown'
                    outputFile.write(
                        f'"{curData.uuid}","{curData.macAddress}","{curData.name}","{curData.company}",'
                        f'"{curData.manufacturer}","{btType}",{curData.rssi},{txPower},{rangeStr},'
                        f'"{curData.lastSeen.strftime("%m/%d/%Y %H:%M:%S")}"\n'
                    )
        finally:
            outputFile.close()
            self.btUpdateLock.release()

        self.statusBar().showMessage(f"Bluetooth data exported to {fileName}")

    # ------------------ File Import & Export Handlers ------------------
    def onClearAllData(self):
        self.onClearWifiData()
        self.onClearBtData()
        self.statusBar().showMessage("Cleared all data.")

    def openFileDialog(self, fileSpec="CSV Files (*.csv);;All Files (*)"):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getOpenFileName(self, "Open File", "", fileSpec, options=options)
        return fileName if fileName else None

    def saveFileDialog(self, fileSpec="CSV Files (*.csv);;All Files (*)"):
        options = QFileDialog.Options()
        options |= QFileDialog.DontUseNativeDialog
        fileName, _ = QFileDialog.getSaveFileName(self, "Save File", "", fileSpec, options=options)
        return fileName if fileName else None

    def onImportIWData(self):
        fileName = self.openFileDialog("iw scan output Files (*.iw *.txt);;All Files (*)")
        if not fileName:
            return

        try:
            with open(fileName, "r") as f:
                fileLines = f.readlines()
        except Exception as e:
            QMessageBox.question(self, 'Error', f"Unable to open {fileName}: {e}", QMessageBox.Ok)
            return

        self.setCursor(Qt.WaitCursor)
        wirelessNetworks = WirelessEngine.parseIWoutput(fileLines) if fileLines else {}
        if wirelessNetworks:
            self.populateTable(wirelessNetworks)
            self.tabs.setCurrentIndex(0)
            self.statusBar().showMessage(f"Imported {len(wirelessNetworks)} networks from {fileName}")
        self.setCursor(Qt.ArrowCursor)

    def onImportJSON(self):
        fileName = self.openFileDialog("JSON Files (*.json);;All Files (*)")
        if not fileName:
            return

        self.setCursor(Qt.WaitCursor)
        try:
            with open(fileName, 'r') as f:
                netDict = json.load(f)
            if 'wifi-aps' not in netDict:
                QMessageBox.question(self, 'Error', "Invalid JSON format (missing 'wifi-aps' root key).", QMessageBox.Ok)
                return

            wirelessNetworks = {}
            for curNet in netDict['wifi-aps']:
                newNet = WirelessNetwork.createFromJsonDict(curNet)
                wirelessNetworks[newNet.getKey()] = newNet

            if wirelessNetworks:
                self.onClearWifiData()
                self.populateTable(wirelessNetworks)
                self.tabs.setCurrentIndex(0)
                self.statusBar().showMessage(f"Imported {len(wirelessNetworks)} networks from {fileName}")
        except Exception as e:
            QMessageBox.question(self, 'Error', f"Unable to parse JSON file: {e}", QMessageBox.Ok)
        finally:
            self.setCursor(Qt.ArrowCursor)

    def onImportCSV(self):
        fileName = self.openFileDialog("CSV Files (*.csv);;All Files (*)")
        if not fileName:
            return

        self.setCursor(Qt.WaitCursor)
        try:
            with open(fileName, 'r') as f:
                reader = csv.reader(f)
                raw_list = [row for row in reader if row]

            if len(raw_list) > 1:
                wirelessNetworks = {}
                for i in range(1, len(raw_list)):
                    row = raw_list[i]
                    if len(row) >= 10:
                        newNet = WirelessNetwork()
                        newNet.macAddr = row[0]
                        newNet.ssid = row[2].replace('"', '') if len(row) > 2 else ''
                        newNet.security = row[3] if len(row) > 3 else ''
                        newNet.privacy = row[4] if len(row) > 4 else ''
                        channelstr = row[5] if len(row) > 5 else '1'
                        if '+' in channelstr:
                            newNet.channel = int(channelstr.split('+')[0])
                            newNet.secondaryChannel = int(channelstr.split('+')[1])
                        else:
                            newNet.channel = int(channelstr) if channelstr.isdigit() else 1
                        newNet.frequency = int(row[6]) if len(row) > 6 and row[6].isdigit() else 2412
                        newNet.signal = int(row[7]) if len(row) > 7 else -90
                        newNet.bandwidth = int(row[9]) if len(row) > 9 and row[9].isdigit() else 20
                        if len(row) > 10:
                            try:
                                newNet.lastSeen = parser.parse(row[10])
                            except Exception:
                                pass
                        if len(row) > 11:
                            try:
                                newNet.firstSeen = parser.parse(row[11])
                            except Exception:
                                pass
                        wirelessNetworks[newNet.getKey()] = newNet

                if wirelessNetworks:
                    self.onClearWifiData()
                    self.populateTable(wirelessNetworks)
                    self.tabs.setCurrentIndex(0)
                    self.statusBar().showMessage(f"Imported {len(wirelessNetworks)} networks from {fileName}")
        except Exception as e:
            QMessageBox.question(self, 'Error', f"Error reading CSV file: {e}", QMessageBox.Ok)
        finally:
            self.setCursor(Qt.ArrowCursor)

    def onExportJSON(self):
        fileName = self.saveFileDialog("JSON Files (*.json);;All Files (*)")
        if not fileName:
            return

        self.updateLock.acquire()
        try:
            numItems = self.networkTable.rowCount()
            netlist = []
            for i in range(0, numItems):
                curData = self.networkTable.item(i, 2).data(Qt.UserRole + 1)
                if curData:
                    netlist.append(curData.toJsondict())

            outputdict = {'wifi-aps': netlist}
            with open(fileName, 'w', encoding='utf-8') as f:
                json.dump(outputdict, f, indent=2)
            self.statusBar().showMessage(f"WiFi scan exported to {fileName}")
        except Exception as e:
            QMessageBox.question(self, 'Error', f"Unable to write JSON to {fileName}: {e}", QMessageBox.Ok)
        finally:
            self.updateLock.release()

    def onExportCSV(self):
        fileName = self.saveFileDialog("CSV Files (*.csv);;All Files (*)")
        if not fileName:
            return

        self.updateLock.acquire()
        try:
            with open(fileName, 'w', newline='', encoding='utf-8') as outputFile:
                outputFile.write('macAddr,vendor,SSID,Security,Privacy,Channel,Frequency,Signal Strength,Bandwidth,% Utilization,# of Stations,Last Seen,First Seen\n')
                numItems = self.networkTable.rowCount()
                for i in range(0, numItems):
                    curData = self.networkTable.item(i, 2).data(Qt.UserRole + 1)
                    if curData:
                        vendor = self.networkTable.item(i, 1).text() if self.networkTable.item(i, 1) else ''
                        outputFile.write(
                            f'"{curData.macAddr}","{vendor}","{curData.ssid}","{curData.security}","{curData.privacy}",'
                            f'{curData.getChannelString()},{curData.frequency},{curData.signal},{curData.bandwidth},'
                            f'{curData.utilization},{curData.stationcount},'
                            f'"{curData.lastSeen.strftime("%m/%d/%Y %H:%M:%S")}","{curData.firstSeen.strftime("%m/%d/%Y %H:%M:%S")}"\n'
                        )
            self.statusBar().showMessage(f"WiFi scan exported to {fileName}")
        except Exception as e:
            QMessageBox.question(self, 'Error', f"Unable to write to {fileName}: {e}", QMessageBox.Ok)
        finally:
            self.updateLock.release()

    def onAbout(self):
        aboutMsg = (
            "Sparrow - WiFi & Bluetooth Scanner\n"
            "Originally written by ghostop14\n"
            "https://github.com/ghostop14\n\n"
            "Displays active WiFi and Bluetooth scans with\n"
            "real-time device discovery, vendor identification, and export."
        )
        QMessageBox.question(self, 'About Sparrow Scanner', aboutMsg, QMessageBox.Ok)

    def closeEvent(self, event):
        # Stop WiFi scan
        if self.scanRunning and self.scanThread:
            self.scanThread.signalStop = True

        # Stop Bluetooth scan
        self.btTimer.stop()
        if self.bluetooth:
            try:
                self.bluetooth.stopDiscovery()
                self.bluetooth.stopScanning()
            except Exception:
                pass

        event.accept()


# ------- Main Routine -------------------------
if __name__ == '__main__':
    dirname, filename = os.path.split(os.path.abspath(__file__))
    if dirname not in sys.path:
        sys.path.insert(0, dirname)

    app = QApplication(sys.argv)
    mainWin = mainWindow()
    result = app.exec_()
    sys.exit(result)
