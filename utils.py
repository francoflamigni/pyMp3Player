import time
import sys
import os
import re
from configparser import ConfigParser
from datetime import date, datetime
from PyQt6.QtCore import Qt, QSortFilterProxyModel
from PyQt6.QtGui import QPixmap, QIcon, QFont, QCursor, QAction, QColor, QPainter, QKeyEvent
from PyQt6.QtWidgets import (QMessageBox, QHBoxLayout, QLabel, QLineEdit, QPushButton, QStyle,
                             QToolButton, QComboBox, QCompleter, QTreeWidgetItem, QRadioButton,
                             QApplication, QBoxLayout, QSpacerItem, QWidgetItem)


def errorMessage(err, titolo='Errore'):
    msg = QMessageBox()
    msg.setWindowTitle(titolo)
    msg.setIcon(QMessageBox.Icon.Critical)
    msg.setText(err)
    msg.exec()


def AddMenuItem(txt, fun, enab=True) -> QAction:
    ac = QAction(txt)
    ac.triggered.connect(fun)
    ac.setEnabled(enab)
    #ctx.addAction(ac)
    return ac


def informMessage(err, titolo='', pitch=0, bold=True, ico=''):
    msg = QMessageBox()
    msg.setWindowTitle(titolo)
    if len(ico) == 0:
        msg.setIcon(QMessageBox.Icon.Information)
    else:
        msg.setIconPixmap(QPixmap(ico))
    if pitch != 0:
        font = QFont()
        font.setPointSize(pitch)
        font.setBold(bold)
        msg.setFont(font)

    msg.raise_()
    txt = ''
    if isinstance(err, list):
        for e in err:
            txt = txt + e + '\n'
    else:
        txt = err
    msg.setText(txt) #err)
    msg.exec()


def yesNoMessage(tit, message):
    msg = QMessageBox()
    msg.setIcon(QMessageBox.Icon.Question)
    msg.setWindowTitle(tit)
    msg.setText(message)
    msg.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
    msg.setDefaultButton(QMessageBox.StandardButton.No)
    retval = msg.exec()
    if retval != QMessageBox.StandardButton.Yes:
        return False
    return True


def center_in_parent(child, parent, dx, dy):
    qr = parent.frameGeometry()
    bx = qr.width()
    by = qr.height()
    x0 = int((bx - dx) / 2) + qr.left()
    y0 = int((by - dy) / 2) + qr.top()
    child.setGeometry(x0, y0, dx, dy)
    child.move(x0, y0)


def form(parent, nome, fun=None, btn_txt='...'):
    h = QHBoxLayout() #parent)
    l = QLabel(nome, parent)
    e = QLineEdit(parent)
    h.addWidget(l)
    h.addWidget(e)
    if fun is not None:
        b = QPushButton(btn_txt, parent)
        b.clicked.connect(lambda x: fun(e))
        h.addWidget(b)
        return e, h, b
    return e, h


def comboForm(parent, nome):
    h = QHBoxLayout() #parent)
    l = QLabel(parent)
    l .setText(nome)
    c = QComboBox(parent)
    h.addWidget(l)
    h.addWidget(c)
    return c, h


def buttons(parent, edit, erase, iconedit, iconerase):
    btnEdit = None
    if edit is not None:
        btnEdit = QPushButton(parent)

        px = QPixmap(iconedit)
        btnEdit.setIcon(QIcon(px))
        btnEdit.clicked.connect(edit)
    btnDel = None
    if erase is not None:
        btnDel = QPushButton(parent)

        px = QPixmap(iconerase)
        btnDel.setIcon(QIcon(px))
        btnDel.clicked.connect(erase)
    if btnEdit is not None:
        if btnDel is not None:
            return btnEdit, btnDel
        else:
            return btnEdit
    else:
        return btnDel


class btn:
    def __init__(self, text='', fun=None, ico=None):
        self.text = text
        self.fun = fun
        self.ico = ico


def lineButtons(parent, list):
    Hlayout = QHBoxLayout() #parent)
    for btn in list:
        if btn.fun is None:
            Hlayout.addStretch(1)
            continue
        bt = QToolButton(parent)
        bt.setText(btn.text)
        if btn.ico is not None:
            bt.setIcon(parent.style().standardIcon(btn.ico))
        bt.clicked.connect(btn.fun)
        Hlayout.addWidget(bt)
    return Hlayout


def exitBtn(parent):
    h = QHBoxLayout() #parent)
    btnOK = QPushButton(parent)
    btnOK.setIcon(parent.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_DialogApplyButton')))
    btnOK.clicked.connect(parent.Ok)
    btnOK.setDefault(True)

    btnAnnulla = QPushButton(parent)
    btnAnnulla.setIcon(parent.style().standardIcon(getattr(QStyle.StandardPixmap, 'SP_DialogCancelButton')))
    btnAnnulla.clicked.connect(parent.Annulla)
    h.addWidget(btnOK)
    h.addWidget(btnAnnulla)
    return h


def newButton(par, ico=None, txt=None, tip=None, ck=None):
    if ck is None:
        b1 = QPushButton(par)
    else:
        b1 = QRadioButton(par)
        b1.setChecked(ck)
    if txt is not None:
        b1.setText(txt)
    if ico is not None:
        px = QPixmap(ico)
        sz = px.size().__mul__(0.8)
        b1.setIcon(QIcon(px))
        b1.setIconSize(sz)
    if tip is not None:
        b1.setToolTip(tip)
    return b1


def clearTable(table):
    table.parent().noChange = True
    while table.rowCount():
        table.removeRow(0)
    table.parent().noChange = False


def clearTree(tree):
    root = tree.invisibleRootItem()
    for i in range(0, root.childCount()):
        root.removeChild(root.child(i))

def waitCursor(on=False):
    if on is True:
        QApplication.setOverrideCursor(QCursor(Qt.CursorShape.WaitCursor))
    else:
        QApplication.restoreOverrideCursor()

class ExtendedComboBox(QComboBox):
    def __init__(self, parent=None):
        super(ExtendedComboBox, self).__init__(parent)
        self.parent = parent

        self.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.setEditable(True)

        # add a filter model to filter matching items
        self.pFilterModel = QSortFilterProxyModel(self)
        self.pFilterModel.setFilterCaseSensitivity(Qt.CaseSensitivity.CaseInsensitive)
        self.pFilterModel.setSourceModel(self.model())

        # add a completer, which uses the filter model
        self.completer = QCompleter(self.pFilterModel, self)
        # always show all (filtered) completions
        self.completer.setCompletionMode(QCompleter.CompletionMode.UnfilteredPopupCompletion)
        self.setCompleter(self.completer)

        # connect signals
        self.lineEdit().textEdited.connect(self.pFilterModel.setFilterFixedString)
        self.completer.activated.connect(self.on_completer_activated)
        self.setEditable(False)

    def hidePopup(self):
        super(ExtendedComboBox, self).hidePopup()
        self.setEditable(False)

    def showPopup(self):
        super(ExtendedComboBox, self).showPopup()
        self.setEditable(True)

    # on selection of an item from the completer, select the corresponding item from combobox
    def on_completer_activated(self, text):
        if text:
            index = self.findText(text)
            self.setCurrentIndex(index)

    # on model change, update the models of the filter and completer as well
    def setModel(self, model):
        super(ExtendedComboBox, self).setModel(model)
        self.pFilterModel.setSourceModel(model)
        self.completer.setModel(self.pFilterModel)

    # on model column change, update the model column of the filter and completer as well
    def setModelColumn(self, column):
        self.completer.setCompletionColumn(column)
        self.pFilterModel.setFilterKeyColumn(column)
        super(ExtendedComboBox, self).setModelColumn(column)


def ts_date(ts):
    format = '%d-%m-%Y'
    try:
        data = datetime.fromtimestamp(ts).strftime(format)
    except Exception as err:
        data = date.today().strftime(format)
    return data


def ts_dateTime(ts):
    format = '%d-%m-%Y %H:%M:%S'
    try:
        data = datetime.fromtimestamp(ts).strftime(format)
    except Exception as err:
        data = date.today().strftime(format)
    return data


def ts_date2(ts):
    tm = datetime.fromtimestamp(ts)
    return tm.year, tm.month, tm.day

def ts_time(ts):
    tm = datetime.fromtimestamp(ts)
    return tm.hour, tm.minute, tm.second

def date_ts(data=None):
    tm = dateTime_ts()
    if data is None:
        return tm
        #today = date.today().strftime('%d-%m-%Y')
    else:
        today = data.replace('/', '-')
        today = today.replace(' ', '-')
        sp = today.split('-')
        if len(sp) < 3:
            return 0
        if len(sp[2]) < 4:
            today = sp[2] + '-' + sp[1] + '-' + sp[0]

    try:
        aa = int(time.mktime(datetime.strptime(today, "%d-%m-%Y").timetuple()))
    except:
        aa = 0
    return aa

def dateTime_ts(ts=None):
    tm = ts
    if tm is None:
        tm = int(time.time())
    return tm


def tree_icon(item, iconPath, color=QColor(255, 216, 108), colorB=QColor('white')):
    pixmapi = QPixmap(iconPath)
    mask = pixmapi.createMaskFromColor(colorB, Qt.MaskMode.MaskOutColor)

    p = QPainter(pixmapi)
    p.setPen(QColor(color))
    p.drawPixmap(pixmapi.rect(), mask, mask.rect())
    p.end()
    #pixmapi.fill(color)
    #pixmapi.setMask(mask)
    icon = QIcon(pixmapi)
    item.setIcon(0, icon)
def find_dates(txt):
    pattern = "\d{2}[/.-]\d{2}[/.-]\d{2,4}"

    dates = re.findall(pattern, txt)
    return dates

def findWholeWord(w):
    return re.compile(r'\b({0})\b'.format(w), flags=re.IGNORECASE).search  #.findall

def find_keyword(txt, keys):
    vkeys = keys.split(',')
    count = 0
    for key in vkeys:
        pattern = '(?i)' + key.strip()  #?i per case insensitive
        dates1 = re.findall(pattern, txt)
        dates = findWholeWord(key.strip())(txt)
        if dates is not None:  # and len(dates) > 0:
            count += 1
    return count == len(vkeys)

def strToFilename(instr):
    fbd = ['/', '\\', '>', '<', ':', '|', '?', '*', '\"']
    out = instr
    for f in fbd:
        out = out.replace(f, '_')
    return out

def add_lev0(tree, d, opt=Qt.ItemFlag.NoItemFlags):
    qi = QTreeWidgetItem()
    nome = d.nome
    if len(nome) == 0:
        nome = 'Nuova categoria'

    qi.setText(0, nome)
    qi.setData(0, Qt.ItemDataRole.UserRole, d)

    qi.setFlags(qi.flags() | opt)
    tree.addTopLevelItem(qi)
    return qi


def add_lev1(sel, d, opt=Qt.ItemFlag.NoItemFlags):
    if sel is None:
        return None

    qi = QTreeWidgetItem()
    nome = d.nome
    if len(nome) == 0:
        nome = 'Nuova categoria'
    qi.setText(0, nome)

    qi.setData(0, Qt.ItemDataRole.UserRole, d)
    qi.setFlags(qi.flags() | opt)
    sel.insertChild(0, qi)
    return qi


def resource_path(dir):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = dir

    return base_path


class iniConf:
    def __init__(self, name):
        self.confName = name
        self.done = False
        self.conf = {}
        self.config_object = ConfigParser()
        if os.path.isfile(self.confName) is True:
            self.config_read()
            self.done = True

    def get(self, k1=None, k2=None):
        if k1 is None:
            return self.config_object.sections()
        if k1 not in self.conf.keys():
            return ''
        sez = self.conf[k1]
        if k2 is None:
            return sez
        if k2 not in sez.keys():
            return ''
        return sez[k2]

    def set(self, sez, key, val):
        if sez not in self.conf:
            self.conf[sez] = {}
        s = self.conf[sez]
        s[key] = val
        a = 0

    def set_sez(self, nome, v):
        self.conf[nome] = v

    def setConf(self, conf):
        self.conf = conf

    def save(self):
        for key in self.conf.keys():
            if self.config_object.has_section(key) is True:
                self.config_object.remove_section(key)
            self.config_object.add_section(key)

        for key1 in self.conf.keys():
            sez = self.conf[key1]
            for key2 in sez.keys():
                ob = sez[key2]
                self.config_object.set(key1, key2, ob)

        with open(self.confName, 'w') as conf:
            self.config_object.write(conf)

    def config_read(self):
        self.config_object.read(self.confName)
        sezs = self.config_object.sections()

        for key1 in sezs:
            sez = self.config_object.options(key1)
            v = {}
            for it in sez:
                v[it] = self.config_object[key1][it]
            self.conf[key1] = v


def basename(nome):
    return os.path.basename(nome)


def basenameNoExt(nome):
    nm, _ = os.path.splitext(nome)
    return os.path.basename(nm)


def extension(nome):
    _, ext = os.path.splitext(nome)
    if len(ext) > 0:
        sp = os.path.basename(ext).split('.')
        if len(sp) > 1:
            return sp[1]
    return None


def getSiblings(item):
    return getChildren(item.parent())


def getChildren(item):
    siblings = []
    if item is None:
        return siblings
    for i in range(0, item.childCount()):
        child = item.child(i)
        if child != item:
            siblings.append(child.text(0))
    return siblings


def getChild(item, txt):
    for i in range(0, item.childCount()):
        child = item.child(i)
        if child.text(0) == txt:
            return child
    return None

def _find_controls(wd, vec):
    if isinstance(wd, QBoxLayout):
        n = wd.count()
        for i in range(n):
            c1 = wd.itemAt(i)
            if isinstance(c1, QWidgetItem):
                c1 = c1.widget()
            _find_controls(c1, vec)
            a = 0
        return
    if isinstance(wd, QSpacerItem):
        return

    chs = wd.children()
    if len(chs) == 0:
        try:
            t = wd.text()
            a = 0
        except:
            pass
        a = type(wd)
        vec.append(wd)
    for ch in chs:
        _find_controls(ch, vec)
        a = 0
    a = 0


def send_key(widget, key, modif=Qt.KeyboardModifier.NoModifier):
    pressEvent = QKeyEvent(QKeyEvent.Type.KeyPress, key, modif)
    releaseEvent = QKeyEvent(QKeyEvent.Type.KeyRelease, key, Qt.KeyboardModifier.NoModifier)
    QApplication.sendEvent(widget, pressEvent)
    QApplication.sendEvent(widget, releaseEvent)
