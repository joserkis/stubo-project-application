# -*- coding: utf-8 -*-

__author__ = 'anosov'

from PyQt4 import QtGui
from PyQt4 import QtCore
from PyQt4.QtCore import pyqtSlot
from functools import partial


class Editor(QtGui.QWidget):
    def __init__(self):
        super(Editor, self).__init__()
        self.resize(600, 300)
        self.setWindowTitle('Text Editor')

        menu = self.make_menu()
        self.tabs = QtGui.QTabWidget()

        vbox = QtGui.QVBoxLayout()
        vbox.addWidget(menu)
        vbox.addWidget(self.tabs)
        self.setLayout(vbox)

        self.pages = list()
        self.current = None
        self.text_edits = list()
        self.text_base = dict()

        self.show()

    def add_text_tab(self, name):
        tab = QtGui.QWidget()
        layout = QtGui.QVBoxLayout(tab)
        text_edit = QtGui.QTextEdit()
        # text_edit.setText(text)
        layout.addWidget(text_edit)
        self.tabs.addTab(tab, name)
        self.tabs.setCurrentIndex(self.tabs.count() - 1)
        return text_edit

    def get_current_text_edit(self):
        w = self.tabs.currentWidget()
        return w.layout().itemAt(0).widget()

    def make_menu(self):
        @pyqtSlot()
        def make_script():
            text_edit = self.add_text_tab('[new]')

        @pyqtSlot()
        def text_changed(text_edit, base_text):
            def action():
                cur_text = unicode(text_edit.toPlainText())
                i = self.tabs.currentIndex()
                title = self.tabs.tabText(i)
                if base_text != cur_text:
                    if title[-2:] != ' *':
                       self.tabs.setTabText(i, title + ' *')
                else:
                    if title[-2:] == ' *':
                       self.tabs.setTabText(i, title[:-2])
            return action


        @pyqtSlot()
        def open_script():
            path = QtGui.QFileDialog.getOpenFileName(self, 'Open', '/home/anosov/Desktop/')
            if not path:
                return
            with open(path, 'r') as f:
                str_ = unicode(f.read(), 'utf8')

            text_edit = self.add_text_tab(path)
            text_edit.setText(str_)
            text_edit.textChanged.connect(text_changed(text_edit, str_))

        def test_script():
            path = '/home/anosov/Desktop/2'
            with open(path, 'r') as f:
                str_ = unicode(f.read(), 'utf8')

            text_edit = self.add_text_tab(path)
            text_edit.setText(str_)
            text_edit.textChanged.connect(text_changed(text_edit, str_))

        def close_script(root):
            if self.tabs.count() == 0:
                return

            i = self.tabs.currentIndex()
            path = self.tabs.tabText(i)

            if path[-2:] == ' *' or path == '[new]' and not self.get_current_text_edit().toPlainText().isEmpty():
                res = QtGui.QMessageBox.question(root, 'Close Question', 'Do you want save it?', QtGui.QMessageBox.Yes | QtGui.QMessageBox.No | QtGui.QMessageBox.Cancel)
                if res == QtGui.QMessageBox.Yes:
                    save_script()
                elif res == QtGui.QMessageBox.Cancel:
                    return
            self.tabs.removeTab(i)

        @pyqtSlot()
        def save_as_script():
            path = QtGui.QFileDialog.getSaveFileName(self, 'Save As ...', '/home/anosov/Desktop/')
            if path:
                text_edit = self.get_current_text_edit()
                text = text_edit.toPlainText().toUtf8()
                with open(path, 'w') as f:
                    f.write(text)
                text_edit.textChanged.connect(text_changed(text_edit, unicode(text, 'utf8')))
                i = self.tabs.currentIndex()
                self.tabs.setTabText(i, path)

        @pyqtSlot()
        def save_script():
            if self.tabs.count() == 0:
                return

            i = self.tabs.currentIndex()
            path = self.tabs.tabText(i)

            if path == '[new]':
                save_as_script()
                return

            if path[-2:] == ' *':
                path = path[:-2]
                text_edit = self.get_current_text_edit()
                text = text_edit.toPlainText().toUtf8()
                with open(path, 'w') as f:
                    f.write(text)
                text_edit.textChanged.connect(text_changed(text_edit, unicode(text, 'utf8')))
                self.tabs.setTabText(i, path)


        menu = QtGui.QMenuBar()
        menu.addAction('New', make_script)
        menu.addAction('Open', open_script)
        menu.addAction('Save', save_script)
        menu.addAction('Save As', save_as_script)
        menu.addAction('Close', partial(close_script, self))
        # menu.addAction('< Test >', test_script)
        return menu


