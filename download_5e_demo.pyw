#!/usr/bin/python
# -*- coding: utf-8 -*-
# TODO: GUI and Chinese Download Progress
# TODO: Multithread
# TODO: No need to download if cancel
# TODO: Internationalization, mostly English
"""
5e demo download
ver 2.2.0
"""
import datetime
import os
import re
import struct
import sys
import zipfile

import requests

from PyQt5.QtWidgets import (QWidget, QLabel, QPushButton, QGridLayout,
                             QHBoxLayout, QLineEdit, QMessageBox,
                             QFileDialog, QApplication)
from PyQt5.QtGui import QIcon
from PyQt5.QtCore import Qt


PLAYER_SEARCH = "https://www.5ewin.com/api/search?keywords={keyword}"
PLAYER_DATA_PAGE = "https://www.5ewin.com/data/player/{0}"
PLAYER_DATA_API = "https://www.5ewin.com/api/data/player_match/{player}/"
CURRENT_YEAR = str(datetime.datetime.now().year)
MATCH_LIST_API = 'https://www.5ewin.com/api/data/match_list/{player}?yyyy=' + CURRENT_YEAR + '&page=%d'

PLAYER_DATA_PAGE_PATTERN = re.compile(r'https?://www\.5ewin\.com/data/player/([A-Za-z0-9_]+)')
PLAYER_ID_PATTERN = re.compile(r'<div id="match-tb" data-uid="(\d+?)">')


def clear_ext(x):
    """
    Get basename without extension
    e.g.
        file:///C:/d/example.txt        -> example
        http://example.com/example.html -> example
        D:\e\f\g.hij                    -> g
    """
    return os.path.splitext(os.path.basename(x))[0]


def find_player(keyword):
    """
    Find player domain from 5e player searching api
    """
    success = False
    while success is False:
        try:
            response = requests.get(PLAYER_SEARCH.format(keyword=keyword))
        except requests.RequestException as request_exception:
            raise request_exception
        player_search_result = response.json()
        success = player_search_result['success']
    result_total = player_search_result['data']['user']['total']
    if result_total < 1:
        return None
    # TODO: let user choose multiple
    else:
        player_id = player_search_result['data']['user']['list'][0]['domain']
        return player_id


def find_player_id(url):
    """
    Find player id from player user page
    """
    response = requests.get(url)
    result = PLAYER_ID_PATTERN.search(response.text)
    return result.group(1)


def percentage(consumed_bytes, total_bytes):
    if total_bytes:
        rate = int(100 * (consumed_bytes / total_bytes))
        print('\r  {0}% '.format(rate), end='')
        sys.stdout.flush()


def create(filename):
    with open(filename, 'w') as fin:
        pass


def download_file(url, local_folder, chunk_size=1024, headers={}):
    consumed = 0
    finished = False
    if not os.path.exists(local_folder):
        os.makedirs(local_folder)
    r = requests.get(url, stream=True, verify=False, headers=headers)
    filename = url.split('/')[-1]
    local_filename = local_folder + filename
    tmp_filename = local_filename + '.tmp'
    try:
        with open(tmp_filename, 'rb') as fin:
            consumed = int(fin.read()) + 1
    except:
        create(tmp_filename)
    finally:
        headers['Range'] = 'bytes=%d-' % consumed
    total_length = r.headers['Content-Length']
    with open(local_filename, 'wb') as f:
        if total_length:
            total_length = int(total_length)
        try:
            for chunk in r.iter_content(chunk_size=chunk_size):
                # filter out keep-alive new chunks
                if chunk:
                    f.write(chunk)
                    consumed += chunk_size
                    # f.flush() commented by recommendation from J.F.Sebastian
                percentage(consumed, total_length)
            finished = True
            os.remove(tmp_filename)
            print('\n  Download Finished.\n')
        except:
            print('Download Failed. Retrying...')
            download_file(url, local_folder, headers=headers)
        finally:
            if not finished:
                with open(tmp_filename, 'wb') as ftmp:
                    ftmp.write(struct.pack('i', consumed))
    return local_filename


def download_and_unzip(downloadlist, local_folder, overwrite_flag, overwriting=None):
    for file in downloadlist:
        if not overwrite_flag and overwriting and clear_ext(file) in overwriting:
            continue
        filename = download_file(file, local_folder)
        with zipfile.ZipFile(filename) as myzip:
            myzip.extractall(path=local_folder)


class Form(QWidget):
    """
    Main Form
    """
    def __init__(self, parent=None):
        super(Form, self).__init__(parent)

        lbl_name = QLabel("请输入玩家用户名或个人战绩页面网址：")
        self.lne_name = QLineEdit()

        button_download = QPushButton("下载")

        button_download.clicked.connect(self.download)
        self.lne_name.returnPressed.connect(button_download.click)

        layout_name = QHBoxLayout()
        layout_name.addWidget(lbl_name)
        layout_name.addWidget(self.lne_name)

        layout_main = QGridLayout()
        layout_main.addLayout(layout_name, 0, 0)
        layout_main.addWidget(button_download, 0, 1)

        self.setLayout(layout_main)
        self.setWindowFlags(Qt.WindowCloseButtonHint | Qt.MSWindowsFixedSizeDialogHint | Qt.WindowTitleHint)
        self.setWindowTitle("5E Demo 批量下载器")
        # No Icon here to avoid copyright problems.
        # self.setWindowIcon(QIcon("app.ico"))

    def download(self):
        """
        Download and Unzip 5E demos
        """
        # Get player id
        player_name = self.lne_name.text()
        result = PLAYER_DATA_PAGE_PATTERN.match(player_name)
        if result:
            # If it is an url starts with http(s)://www.5ewin.com/data/player/
            try:
                player_id = result.group(1)  # player_id is the last segment of player's data page url
            except IndexError:
                QMessageBox.critical(self, "错误", "网址解析失败。")
                return
        else:
            # Try user name
            try:
                player_id = find_player(player_name)
            except requests.RequestException:
                QMessageBox.information(self, "错误", "网络请求失败。")
                return
        if not player_id:
            try:
                if requests.get(PLAYER_DATA_PAGE).status_code == 404:
                    QMessageBox.information(self, "错误", "无法找到该玩家，您的输入有误，请重试。")
                    return
                else:
                    # It is player_id
                    # FIXME: Not working e.g. 365208xviib7
                    player_id = player_name
            except requests.RequestException:
                QMessageBox.information(self, "错误", "网络请求失败。")
                return
        # TODO: Last year support needed
        match_list_url = MATCH_LIST_API.format(player=player_id)
        page_count = 0
        matches = []
        while True:
            cur_page = requests.get(match_list_url % (page_count + 1)).json()
            if 'data' in cur_page:
                if cur_page['data']:
                    # pages.insert(page_count, cur_page)
                    # items += cur_page['data']
                    matches += cur_page['data']
                else:
                    # if cur_page['data'] == None
                    break
            page_count += 1

        # Turn match objects to list of demo download url
        download_list = []
        for match in matches:
            if 'demo_url' in match:
                if match['demo_url']:
                    download_list.append(match["demo_url"])

        # Start confirming and downloading
        if QMessageBox.question(self, "下载", "您有 %d 个 demo 可供下载，继续吗？" % len(download_list), QMessageBox.Yes | QMessageBox.No) == QMessageBox.No:
            return
        save_at = QFileDialog.getExistingDirectory(self, "请选择 dem 保存目录")

        download_names = map(clear_ext, download_list)
        existed_items = map(clear_ext, [x for x in os.listdir(save_at) if x.endswith(".dem")])
        searching = list(existed_items)  # exisited but not overwriting with checked names. existed_items - searching = overwrting with checked names
        overwriting = []
        for name in download_names:
            for item in searching:
                if item == name:
                    # if an item in dowload_list is existing already
                    # existed_items.remove(item)
                    searching.remove(item)
                    overwriting.append(item)

        if overwriting:
            ret = QMessageBox.question(self, "是否覆盖", "检测到当前文件夹下有 %d 个 demo 已存在，覆盖吗？\n\n选择“是”则覆盖，“否”则跳过，“取消”则取消下载。" % len(overwriting), QMessageBox.Yes | QMessageBox.No | QMessageBox.Cancel)
            if ret == QMessageBox.Yes:
                overwrite_flag = True
            elif ret == QMessageBox.No:
                overwrite_flag = False
            elif ret == QMessageBox.Cancel:
                return
        download_and_unzip(download_list, save_at, overwrite_flag, overwriting)
        QMessageBox.information(self, "提示", "下载完成")


def main():
    """
    Initialize PyQt Application
    """
    app = QApplication(sys.argv)
    form_main = Form()
    form_main.show()
    sys.exit(app.exec_())

if __name__ == "__main__":
    main()
