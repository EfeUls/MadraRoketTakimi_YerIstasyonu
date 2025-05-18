import sys
import hashlib
from PyQt5 import uic
from PyQt5.QtWidgets import QApplication, QWidget, QMessageBox, QLabel, QVBoxLayout, QPushButton 
from PyQt5.QtGui import QPixmap, QColor
from PyQt5.QtCore import Qt, QUrl, pyqtSignal, QThread, QTimer
from matplotlib.figure import Figure
from matplotlib.backends.backend_qt5agg import FigureCanvasQTAgg as FigureCanvas
import sqlite3
import serial
from PyQt5.QtWebEngineWidgets import QWebEngineView
import serial.tools.list_ports
from datetime import datetime
import pyqtgraph as pg
import traceback
from PyQt5.QtCore import QObject
import os
from PyQt5.QtWidgets import QWidget
from PyQt5.QtWebEngineWidgets import QWebEngineView
from PyQt5.QtCore import QUrl, QTimer
from PyQt5 import uic
import os
# Uygulamanın çalıştığı ana dizin
BASE_DIR = os.path.dirname(os.path.abspath(__file__))

# Veritabanı dosya yolları
VERITABANI_ADI = os.path.join(BASE_DIR, "admin_verileri.db")
VERITABANI_UCUS = os.path.join(BASE_DIR, "ucus_verileri.db") # Uçuş verileri için

# --- Admin Veritabanı Fonksiyonları ---
def baglanti_olustur():
    conn = None
    try:
        conn = sqlite3.connect(VERITABANI_ADI)
        return conn
    except sqlite3.Error as e:
        print(f"Admin veritabanı bağlantı hatası: {e}")
    return conn

def sifre_hashle(sifre):
    return hashlib.sha256(sifre.encode()).hexdigest()

def tablo_olustur():
    conn = baglanti_olustur()
    if conn is not None:
        try:
            cursor = conn.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS admin_verileri (
                    kullanici_adi TEXT UNIQUE NOT NULL,
                    sifre TEXT NOT NULL
                )
            """)
            conn.commit()
            print("admin_verileri tablosu oluşturuldu veya zaten mevcut.")
        except sqlite3.Error as e:
            print(f"Admin tablosu oluşturma hatası: {e}")
        finally:
            conn.close()

# --- Uçuş Veritabanı Fonksiyonları ---
def baglanti_olustur_ucus():
    conn_ucus = None
    try:
        conn_ucus = sqlite3.connect(VERITABANI_UCUS)
        return conn_ucus
    except sqlite3.Error as e:
        print(f"Uçuş veritabanı bağlantı hatası: {e}")
    return conn_ucus

def ucus_tablosu_olustur():
    conn_ucus = baglanti_olustur_ucus()
    if conn_ucus is not None:
        try:
            cursor = conn_ucus.cursor()
            cursor.execute("""
                CREATE TABLE IF NOT EXISTS roket_telemetri (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    kayit_zamani TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                    sayac TEXT,
                    gyro_x REAL,
                    gyro_y REAL,
                    gyro_z REAL,
                    ivme_x REAL,
                    ivme_y REAL,
                    ivme_z REAL,
                    irtifa REAL,
                    paket_no TEXT, -- parcalar[8] için
                    gps_enlem REAL,
                    gps_boylam REAL,
                    gps_irtifa REAL,
                    durum TEXT
                )
            """)
            conn_ucus.commit()
            print("roket_telemetri tablosu (ucus_verileri.db) oluşturuldu veya zaten mevcut.")
        except sqlite3.Error as e:
            print(f"Uçuş tablosu oluşturma hatası: {e}")
        finally:
            conn_ucus.close()

class Worker(QObject):
    veri_geldi = pyqtSignal(str, str)

    def __init__(self, port_name, baud_rate):
        super().__init__()
        self.port_name = port_name
        self.baud_rate = baud_rate
        self.seri_port = None
        self.is_running = True

    def run(self):
        try:
            self.seri_port = serial.Serial(self.port_name, self.baud_rate, timeout=0.2)
            if self.seri_port.is_open:
                print(f"{self.port_name} portu açıldı.")
                while self.is_running:
                    if self.seri_port.in_waiting > 0:
                        try:
                            veri = self.seri_port.readline().decode('utf-8').strip()
                            if veri:
                                self.veri_geldi.emit(self.port_name, veri)
                        except UnicodeDecodeError:
                            print(f"{self.port_name} portundan okunan veri UTF-8 formatında değil.")
                        except Exception as e:
                            print(f"{self.port_name} okuma sırasında hata: {e}")
                    else:
                        QThread.msleep(10)
            else:
                print(f"{self.port_name} portu açılamadı.")
        except serial.SerialException as e:
            print(f"{self.port_name} portu hatası: {e}")
        except Exception as e:
            print(f"Worker ({self.port_name}) çalışma hatası: {e}")
        finally:
            self.stop()

    def stop(self):
        self.is_running = False
        if self.seri_port and self.seri_port.is_open:
            self.seri_port.close()
            print(f"{self.port_name} portu kapatıldı.")


# UI dosyalarının ve görsellerin yolları
UI_ANA_EKRAN = os.path.join(BASE_DIR, "ekran_dosyalari", "ana_ekran.ui")
UI_GRAFIK_EKRAN = os.path.join(BASE_DIR, "ekran_dosyalari", "grafik_ekran.ui")
UI_GPS_EKRAN = os.path.join(BASE_DIR, "ekran_dosyalari", "gps_ekrani.ui")
UI_GIRIS_EKRANI = os.path.join(BASE_DIR, "ekran_dosyalari", "girisekrani.ui")
UI_KAYIT_EKRANI = os.path.join(BASE_DIR, "ekran_dosyalari", "kayitekrani.ui")
LOGO_MADRA = os.path.join(BASE_DIR, "gorseller", "madralogo.png")


class Pencere(QWidget):
    veri_geldi_roket = pyqtSignal(list)
    veri_geldi_payload = pyqtSignal(list)
    veri_geldi_hyi = pyqtSignal(list)

    def __init__(self):
        super().__init__()
        try:
            uic.loadUi(UI_ANA_EKRAN, self)
            self.logoGoster()
        except FileNotFoundError:
            print(f"{UI_ANA_EKRAN} dosyasi bulunamadi!")
            app.exit(1)
        except Exception as e:
            print(f"UI yüklenirken hata oluştu: {e}")
            app.exit(1)

        self.setWindowTitle("Ana Veri Penceresi")
        self.gpsEkran()
        self.portlari_listele()
        self.btnRoketBaglan.clicked.connect(self.roket_baglan)
        self.btnRoketKes.clicked.connect(self.roket_kes)
        self.btnPayloadBaglan.clicked.connect(self.payload_baglan)
        self.btnPayloadKes.clicked.connect(self.payload_kes)
        self.btnHYIBaglan.clicked.connect(self.hyi_baglan)
        self.btnHYIKes.clicked.connect(self.hyi_kes)
        self.baglantiRoket.setStyleSheet("background-color: red;")
        self.baglantiPayload.setStyleSheet("background-color: red;")
        self.baglantiHYI.setStyleSheet("background-color: red;")
        self.butonVeriSil.clicked.connect(self.veritabani_temizle)

        self.yonelim_verileri_x_ekseni = []
        self.yonelim_verileri_y_ekseni = []
        self.grafik_olustur()

        self.gonderButton.clicked.connect(self.konum_goster)
        self.grap_button.clicked.connect(self.graphic_window)
        self.gps_button.clicked.connect(self.gps_window)
        self.irtifaLineEdit.setText(str(0))

        self.veri_geldi_roket.connect(self.roket_verilerini_guncelle)
        self.veri_geldi_payload.connect(self.payload_verilerini_guncelle)
        self.veri_geldi_hyi.connect(self.hyi_verilerini_guncelle)

        self.threads = {}

        # Uçuş kaydı için eklenenler
        self.ucus_veri_kaydi_aktif = False
        self.ucus_db_conn = None

        if hasattr(self, 'ucusBaslatButton') and hasattr(self, 'ucusDurdurButton'):
            self.ucusBaslatButton.clicked.connect(self.ucus_baslat)
            self.ucusDurdurButton.clicked.connect(self.ucus_durdur)
            self.ucusDurdurButton.setEnabled(False)
            self.ucusBaslatButton.setEnabled(True)
        else:
            print("UYARI: ucusBaslatButton veya ucusDurdurButton UI dosyasında bulunamadı.")
            # Örnek: Manuel buton oluşturma (bir layout'a eklenmeli)
            # self.ucusBaslatButton = QPushButton("Uçuş Kaydını Başlat", self)
            # self.ucusDurdurButton = QPushButton("Uçuş Kaydını Durdur", self)
            # self.verticalLayout_or_some_other_layout.addWidget(self.ucusBaslatButton) 
            # self.verticalLayout_or_some_other_layout.addWidget(self.ucusDurdurButton)
            # self.ucusBaslatButton.clicked.connect(self.ucus_baslat)
            # self.ucusDurdurButton.clicked.connect(self.ucus_durdur)
            # self.ucusDurdurButton.setEnabled(False)

    def veritabani_temizle(self):
        yanit = QMessageBox.question(
        self,
        "Verileri Sil",
        "Tüm uçuş verileri silinecek. Emin misiniz?",
        QMessageBox.Yes | QMessageBox.No
    )

        if yanit == QMessageBox.Yes:
            try:
                conn = sqlite3.connect("ucus_verileri.db")
                cursor = conn.cursor()
    
                # Tabloların adlarını senin projenin yapısına göre güncelle
                cursor.execute("DELETE FROM roket_telemetri")
                #cursor.execute("DELETE FROM payload_telemetri")
                #cursor.execute("DELETE FROM hyi_telemetri")
    
                conn.commit()
                conn.close()
                QMessageBox.information(self, "Başarılı", "Veriler başarıyla silindi.")
            except sqlite3.Error as e:
                QMessageBox.critical(self, "Hata", f"Veritabanı hatası: {e}")
            
    def closeEvent(self, event):
        print("Pencere kapatılıyor...")
        if self.ucus_veri_kaydi_aktif:
            self.ucus_durdur()

        for port_name in list(self.threads.keys()):
            thread_data = self.threads.get(port_name)
            if thread_data:
                print(f"{port_name} ({thread_data['cihaz_tipi']}) için durdurma işlemi başlatılıyor.")
                self.durdur_seri_okuma_port_adi_ile(port_name)
        event.accept()

    def graphic_window(self):
        self.gr = grafikEkrani(parent=self)
        self.gr.show()

    def gps_window(self):
        self.gpss = gpss_ekrani(parent=self)
        self.gpss.show()

    def logoGoster(self):
        width = 250
        height = 250
        try:
            pixmap = QPixmap(LOGO_MADRA).scaled(width, height, Qt.KeepAspectRatio)
            if hasattr(self, 'logoLabel'): self.logoLabel.setPixmap(pixmap)
            if hasattr(self, 'logoLabel_2'): self.logoLabel_2.setPixmap(pixmap)
            if hasattr(self, 'logoLabel_3'): self.logoLabel_3.setPixmap(pixmap)
        except Exception as e:
            print(f"Logo yüklenirken hata: {e} (Dosya yolu: {LOGO_MADRA})")

    def gpsEkran(self):
        if hasattr(self, 'RoketGPSWidget'):
            self.harita = QWebEngineView() 
            layout = self.RoketGPSWidget.layout()
            if layout is None: # Eğer layout yoksa, yeni bir tane oluştur
                layout = QVBoxLayout(self.RoketGPSWidget)
                self.RoketGPSWidget.setLayout(layout)
            
            while layout.count():
                child = layout.takeAt(0)
                if child.widget():
                    child.widget().deleteLater()
            
            layout.addWidget(self.harita)
            self.harita.load(QUrl("https://www.google.com/maps"))
        else:
            print("UYARI: RoketGPSWidget UI dosyasında bulunamadı.")


    def konum_goster(self):
        try:
            enlem_str = self.enlemTextbox.toPlainText()
            boylam_str = self.boylamTextbox.toPlainText()
            if not enlem_str or not boylam_str:
                QMessageBox.warning(self, "Uyarı", "Enlem ve boylam boş bırakılamaz.")
                return
            enlem = float(enlem_str)
            boylam = float(boylam_str)
            self.konumGuncelle(enlem, boylam)
        except ValueError:
            QMessageBox.warning(self, "Hata", "Geçersiz enlem veya boylam girdisi. Lütfen sayısal değerler girin.")

    def konumGuncelle(self, enlem, boylam):
        js_code = f"document.location.href = `https://www.google.com/maps?q={enlem},{boylam}&hl=es;z=14&amp;output=embed`"
        # js_code = f"window.location.href = 'https://www.google.com/maps/@{enlem},{boylam},15z';" # Bu da bir seçenek
        if hasattr(self, 'harita') and self.harita:
             self.harita.page().runJavaScript(js_code)
             # self.harita.setUrl(QUrl(f"https://www.google.com/maps?q={enlem},{boylam}&z=15"))
        else:
            print("Harita objesi bulunamadı.")

    def portlari_listele(self):
        BaudRate = [9600, 19200, 38400, 57600, 115200]
        try:
            ports = serial.tools.list_ports.comports()
            self.comboBoxRoket.clear()
            self.comboBoxPayload.clear()
            self.comboBoxHYI.clear()
            for port in sorted(ports, key=lambda p: p.device):
                if hasattr(port, 'device'):
                    self.comboBoxRoket.addItem(port.device)
                    self.comboBoxPayload.addItem(port.device)
                    self.comboBoxHYI.addItem(port.device)
        except Exception as e:
            QMessageBox.critical(self, "Hata", f"Seri portlar listelenirken hata oluştu: {e}")

        self.comboBoxRateRoket.clear()
        self.comboBoxRatePayload.clear()
        self.comboBoxRateHYI.clear()
        for rate in BaudRate:
            self.comboBoxRateRoket.addItem(str(rate))
            self.comboBoxRatePayload.addItem(str(rate))
            self.comboBoxRateHYI.addItem(str(rate))
        default_baud_index = BaudRate.index(115200) if 115200 in BaudRate else 0
        self.comboBoxRateRoket.setCurrentIndex(default_baud_index)
        self.comboBoxRatePayload.setCurrentIndex(default_baud_index)
        self.comboBoxRateHYI.setCurrentIndex(default_baud_index)

    def roket_baglan(self):
        port_adi = self.comboBoxRoket.currentText()
        if not port_adi: QMessageBox.warning(self, "Uyarı", "Roket için bir port seçin."); return
        baud_hizi = int(self.comboBoxRateRoket.currentText())
        self.baslat_seri_okuma(port_adi, baud_hizi, 'Roket')

    def roket_kes(self): self.durdur_seri_okuma_cihaz_tipi_ile('Roket')
    def payload_baglan(self):
        port_adi = self.comboBoxPayload.currentText()
        if not port_adi: QMessageBox.warning(self, "Uyarı", "Payload için bir port seçin."); return
        baud_hizi = int(self.comboBoxRatePayload.currentText())
        self.baslat_seri_okuma(port_adi, baud_hizi, 'Payload')

    def payload_kes(self): self.durdur_seri_okuma_cihaz_tipi_ile('Payload')
    def hyi_baglan(self):
        port_adi = self.comboBoxHYI.currentText()
        if not port_adi: QMessageBox.warning(self, "Uyarı", "HYI için bir port seçin."); return
        baud_hizi = int(self.comboBoxRateHYI.currentText())
        self.baslat_seri_okuma(port_adi, baud_hizi, 'HYI')
    def hyi_kes(self): self.durdur_seri_okuma_cihaz_tipi_ile('HYI')

    def baslat_seri_okuma(self, port_name, baud_rate, cihaz_tipi):
        if port_name in self.threads:
            QMessageBox.warning(self, "Uyarı", f"{cihaz_tipi} ({port_name}) için zaten bir bağlantı var.")
            return
        for p, data in self.threads.items():
            if data['cihaz_tipi'] == cihaz_tipi:
                QMessageBox.warning(self, "Uyarı", f"{cihaz_tipi} zaten başka bir port ({p}) üzerinden bağlı.")
                return
        thread = QThread()
        worker = Worker(port_name, baud_rate)
        worker.moveToThread(thread)
        thread.started.connect(worker.run)
        worker.veri_geldi.connect(self.veri_alindi)
        self.threads[port_name] = {'thread': thread, 'worker': worker, 'cihaz_tipi': cihaz_tipi}
        thread.start()
        print(f"{cihaz_tipi} ({port_name}) için seri okuma başlatıldı.")
        if cihaz_tipi == 'Roket': self.baglantiRoket.setStyleSheet("background-color: green;")
        elif cihaz_tipi == 'Payload': self.baglantiPayload.setStyleSheet("background-color: green;")
        elif cihaz_tipi == 'HYI': self.baglantiHYI.setStyleSheet("background-color: green;")

    def durdur_seri_okuma_cihaz_tipi_ile(self, cihaz_tipi_aranan):
        port_to_stop = None
        for p_name, data in self.threads.items():
            if data['cihaz_tipi'] == cihaz_tipi_aranan: port_to_stop = p_name; break
        if port_to_stop: self.durdur_seri_okuma_port_adi_ile(port_to_stop)
        else: QMessageBox.warning(self, "Uyarı", f"{cihaz_tipi_aranan} için aktif bir bağlantı bulunamadı.")

    def durdur_seri_okuma_port_adi_ile(self, port_name):
        if port_name in self.threads:
            thread_data = self.threads.pop(port_name)
            worker, thread, cihaz_tipi = thread_data['worker'], thread_data['thread'], thread_data['cihaz_tipi']
            print(f"{cihaz_tipi} ({port_name}) için okuma durduruluyor...")
            worker.stop(); thread.quit()
            if not thread.wait(2000): print(f"Uyarı: {cihaz_tipi} ({port_name}) thread'i zamanında sonlandırılamadı.")
            else: print(f"{cihaz_tipi} ({port_name}) thread'i başarıyla sonlandırıldı.")
            worker.deleteLater(); thread.deleteLater()
            print(f"{cihaz_tipi} ({port_name}) okuma durduruldu.")
            if cihaz_tipi == 'Roket': self.baglantiRoket.setStyleSheet("background-color: red;")
            elif cihaz_tipi == 'Payload': self.baglantiPayload.setStyleSheet("background-color: red;")
            elif cihaz_tipi == 'HYI': self.baglantiHYI.setStyleSheet("background-color: red;")

    def veri_alindi(self, port_name, veri):
        if port_name not in self.threads: return
        cihaz_tipi = self.threads[port_name]['cihaz_tipi']
        parcalar = veri.split('/')
        if cihaz_tipi == 'Roket' and len(parcalar) == 13: self.veri_geldi_roket.emit(parcalar)
        elif cihaz_tipi == 'Payload' and len(parcalar) == 8: self.veri_geldi_payload.emit(parcalar)
        elif cihaz_tipi == 'HYI' and len(parcalar) == 5: self.veri_geldi_hyi.emit(parcalar)
        else: print(f"Hatalı veri formatı ({cihaz_tipi} @ {port_name}, parça: {len(parcalar)}): {veri}")

    def grafik_olustur(self):
        self.figure = Figure(figsize=(5, 3), dpi=100)
        self.canvas = FigureCanvas(self.figure)
        if hasattr(self, 'aaLayout'):
            while self.aaLayout.count():
                child = self.aaLayout.takeAt(0)
                if child.widget(): child.widget().deleteLater()
            self.aaLayout.addWidget(self.canvas)
        else: print("Uyarı: aaLayout bulunamadı. Matplotlib grafiği eklenemedi."); return
        self.ax_main_graph = self.figure.add_subplot(111)
        self.main_graph_line, = self.ax_main_graph.plot([], [], 'r-')
        self.ax_main_graph.set_title("Roket Açı"); self.ax_main_graph.set_xlabel("Örnek No"); self.ax_main_graph.set_ylabel("ACİ")
        self.figure.tight_layout()

    def roket_verilerini_guncelle(self, parcalar):
        try:
            self.sayacLineEdit.setText(parcalar[0])
            self.gyroXLineEdit.setText(parcalar[1])
            self.gyroYLineEdit.setText(parcalar[2])
            self.gyroZLineEdit.setText(parcalar[3])
            self.ivmeXLineEdit.setText(parcalar[4])
            self.ivmeYLineEdit.setText(parcalar[5])
            self.ivmeZLineEdit.setText(parcalar[6])
            self.irtifaLineEdit.setText(parcalar[7])
            self.roketGPSEnlemLineEdit.setText(parcalar[9]) # parcalar[8] atlandı (paket_no için)
            self.roketGPSBoylamLineEdit.setText(parcalar[10])
            self.roketGPSIrtifaLineEdit.setText(parcalar[11])
            self.durumLineEdit.setText(parcalar[12])

            if self.ucus_veri_kaydi_aktif: # Uçuş kaydı
                self.kaydet_roket_verisi(parcalar)

            try: # Matplotlib grafik güncelleme
                gyro_x_degeri = float(parcalar[1])
                self.yonelim_verileri_y_ekseni.append(gyro_x_degeri)
                self.yonelim_verileri_x_ekseni.append(len(self.yonelim_verileri_x_ekseni))
                max_pencere = 100
                if len(self.yonelim_verileri_y_ekseni) > max_pencere:
                    self.yonelim_verileri_y_ekseni.pop(0)
                    self.yonelim_verileri_x_ekseni.pop(0)
                    self.yonelim_verileri_x_ekseni = list(range(len(self.yonelim_verileri_y_ekseni)))
                self.grafik_guncelle_matplotlib()
            except ValueError: print("Geçersiz gyroX değeri (grafik).")
            # except IndexError: print("Grafik için eksik veri.") # Üstteki try/except'te yakalanır
        except IndexError: print(f"Roket verileri günc. eksik veri (parça: {len(parcalar)}). Beklenen: 13.")
        except ValueError: print("Roket verileri günc. geçersiz sayısal veri.") # Nadir
        except Exception as e: print(f"Roket arayüz günc. hatası: {e}"); traceback.print_exc()

    def payload_verilerini_guncelle(self, parcalar):
        try:
            self.payLoadSayacLineEdit.setText(parcalar[0])
            self.payLoadSicaklikLineEdit.setText(parcalar[1])
            self.payLoadBasincLineEdit.setText(parcalar[2])
            self.payLoadNemLineEdit.setText(parcalar[3])
            self.payLoadGPSEnlemLineEdit.setText(parcalar[4])
            self.payLoadGPSBoylamLineEdit.setText(parcalar[5])
            self.payLoadGPSIrtifaLineEdit.setText(parcalar[6])
            self.payLoadDurumLineEdit.setText(parcalar[7])
        except IndexError: print(f"Payload verileri günc. eksik veri (parça: {len(parcalar)}). Beklenen: 8.")
        except Exception as e: print(f"Payload Arayüz günc. hatası: {e}"); traceback.print_exc()

    def hyi_verilerini_guncelle(self, parcalar):
        try:
            self.hyiSayacLineEdit.setText(parcalar[0])
            self.hyiGForceLineEdit.setText(parcalar[1])
            self.hyiBasincLineEdit.setText(parcalar[2])
            self.hyiGPSEnlemLineEdit.setText(parcalar[3])
            self.hyiGPSBoylamLineEdit.setText(parcalar[4])
        except IndexError: print(f"HYI verileri günc. eksik veri (parça: {len(parcalar)}). Beklenen: 5.")
        except Exception as e: print(f"HYI Arayüz günc. hatası: {e}"); traceback.print_exc()

    def grafik_guncelle_matplotlib(self):
        if not hasattr(self, 'main_graph_line'): return
        self.main_graph_line.set_xdata(self.yonelim_verileri_x_ekseni)
        self.main_graph_line.set_ydata(self.yonelim_verileri_y_ekseni)
        if self.yonelim_verileri_x_ekseni: self.ax_main_graph.set_xlim(min(self.yonelim_verileri_x_ekseni), max(self.yonelim_verileri_x_ekseni))
        if self.yonelim_verileri_y_ekseni:
            min_y, max_y = min(self.yonelim_verileri_y_ekseni), max(self.yonelim_verileri_y_ekseni)
            padding = (max_y - min_y) * 0.1 if (max_y - min_y) > 0 else 1
            self.ax_main_graph.set_ylim(min_y - padding, max_y + padding)
        self.canvas.draw()

    # --- Uçuş Kaydı Metotları ---
    def ucus_baslat(self):
        if self.ucus_veri_kaydi_aktif: QMessageBox.information(self, "Bilgi", "Uçuş kaydı zaten aktif."); return
        self.ucus_db_conn = baglanti_olustur_ucus()
        if self.ucus_db_conn is None:
            QMessageBox.critical(self, "Veritabanı Hatası", "Uçuş veritabanına bağlanılamadı. Kayıt başlatılamıyor.")
            return
        self.ucus_veri_kaydi_aktif = True
        if hasattr(self, 'ucusBaslatButton') and hasattr(self, 'ucusDurdurButton'):
            self.ucusBaslatButton.setEnabled(False); self.ucusDurdurButton.setEnabled(True)
        QMessageBox.information(self, "Uçuş Kaydı", "Roket verileri kaydı başlatıldı.")
        print("Uçuş veri kaydı BAŞLATILDI.")

    def ucus_durdur(self):
        if not self.ucus_veri_kaydi_aktif: QMessageBox.information(self, "Bilgi", "Uçuş kaydı zaten durdurulmuş."); return
        self.ucus_veri_kaydi_aktif = False
        if hasattr(self, 'ucusBaslatButton') and hasattr(self, 'ucusDurdurButton'):
            self.ucusBaslatButton.setEnabled(True); self.ucusDurdurButton.setEnabled(False)
        if self.ucus_db_conn: self.ucus_db_conn.close(); self.ucus_db_conn = None
        QMessageBox.information(self, "Uçuş Kaydı", "Roket verileri kaydı durduruldu.")
        print("Uçuş veri kaydı DURDURULDU.")

    def kaydet_roket_verisi(self, parcalar_str):
        if not self.ucus_veri_kaydi_aktif or self.ucus_db_conn is None: return
        try:
            def to_float_or_none(v): return float(v) if v and v.strip() else None # Basit try/except float için
            try:
                sayac = parcalar_str[0]
                gyro_x = to_float_or_none(parcalar_str[1])
                gyro_y = to_float_or_none(parcalar_str[2])
                gyro_z = to_float_or_none(parcalar_str[3])
                ivme_x = to_float_or_none(parcalar_str[4])
                ivme_y = to_float_or_none(parcalar_str[5])
                ivme_z = to_float_or_none(parcalar_str[6])
                irtifa = to_float_or_none(parcalar_str[7])
                paket_no = parcalar_str[8] # String olarak sakla
                gps_enlem = to_float_or_none(parcalar_str[9])
                gps_boylam = to_float_or_none(parcalar_str[10])
                gps_irtifa = to_float_or_none(parcalar_str[11])
                durum = parcalar_str[12]
            except (ValueError, TypeError) as e_convert: # float dönüşüm hatası
                print(f"Veri dönüştürme hatası (kayıt): {e_convert} - Veri: {parcalar_str}")
                return # Hatalı veri ise kaydetme

            cursor = self.ucus_db_conn.cursor()
            cursor.execute("""
                INSERT INTO roket_telemetri (sayac, gyro_x, gyro_y, gyro_z, ivme_x, ivme_y, ivme_z,
                irtifa, paket_no, gps_enlem, gps_boylam, gps_irtifa, durum)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (sayac, gyro_x, gyro_y, gyro_z, ivme_x, ivme_y, ivme_z, irtifa, paket_no,
                 gps_enlem, gps_boylam, gps_irtifa, durum))
            self.ucus_db_conn.commit()
        except sqlite3.Error as e: print(f"SQLite ('ucus_verileri.db') kayıt hatası: {e}")
        except IndexError: print(f"Veri kaydı sırasında eksik veri (parça: {len(parcalar_str)}). Beklenen: 13.")
        except Exception as e: print(f"Beklenmedik hata ('ucus_verileri.db' kayıt): {e}"); traceback.print_exc()


class grafikEkrani(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.ana_pencere = parent
        try:
            uic.loadUi(UI_GRAFIK_EKRAN, self)
        except Exception as e:
            print(f"Grafik Ekranı UI yüklenirken hata: {e}")
            return

        self.setWindowTitle("Gerçek Zamanlı Sensör Grafikleri")
        self.logo_goster_grafik()
        self.max_pencere = 200

        # Grafik nesnelerini oluştur
        self.irtifa_grafik_widget = self.irtifa_grafik  # UI'dan gelen widget'ları kullan
        self.gyro_x_grafik_widget = self.gyro_x_grafik
        self.gyro_y_grafik_widget = self.gyro_y_grafik
        self.gyro_z_grafik_widget = self.gyro_z_grafik
        self.ivme_x_grafik_widget = self.ivme_x_grafik
        self.ivme_y_grafik_widget = self.ivme_y_grafik
        self.ivme_z_grafik_widget = self.ivme_z_grafik

        self.grafigi_ayarla(self.irtifa_grafik_widget, "İrtifa (m)", "Örnek No", "İrtifa", 'b')
        self.grafigi_ayarla(self.gyro_x_grafik_widget, "Gyro X", "Örnek No", "Gyro X", 'r')
        self.grafigi_ayarla(self.gyro_y_grafik_widget, "Gyro Y", "Örnek No", "Gyro Y", 'g')
        self.grafigi_ayarla(self.gyro_z_grafik_widget, "Gyro Z", "Örnek No", "Gyro Z", 'm')
        self.grafigi_ayarla(self.ivme_x_grafik_widget, "İvme X", "Örnek No", "İvme X", 'c')
        self.grafigi_ayarla(self.ivme_y_grafik_widget, "İvme Y", "Örnek No", "İvme Y", 'y')
        self.grafigi_ayarla(self.ivme_z_grafik_widget, "İvme Z", "Örnek No", "İvme Z", 'k')

        # Veri listelerini başlat
        self.irtifa_x, self.irtifa_y = [], []
        self.gyro_x_x, self.gyro_x_y = [], []
        self.gyro_y_x, self.gyro_y_y = [], []
        self.gyro_z_x, self.gyro_z_y = [], []
        self.ivme_x_x, self.ivme_x_y = [], []
        self.ivme_y_x, self.ivme_y_y = [], []
        self.ivme_z_x, self.ivme_z_y = [], []

        # Eğrileri oluştur
        self.irtifa_egrisi = self.irtifa_grafik_widget.plot(self.irtifa_x, self.irtifa_y, pen=pg.mkPen('b', width=2), name="İrtifa")
        self.gyro_x_egrisi = self.gyro_x_grafik_widget.plot(self.gyro_x_x, self.gyro_x_y, pen=pg.mkPen('r', width=2), name="Gyro X")
        self.gyro_y_egrisi = self.gyro_y_grafik_widget.plot(self.gyro_y_x, self.gyro_y_y, pen=pg.mkPen('g', width=2), name="Gyro Y")
        self.gyro_z_egrisi = self.gyro_z_grafik_widget.plot(self.gyro_z_x, self.gyro_z_y, pen=pg.mkPen('m', width=2), name="Gyro Z")
        self.ivme_x_egrisi = self.ivme_x_grafik_widget.plot(self.ivme_x_x, self.ivme_x_y, pen=pg.mkPen('c', width=2), name="İvme X")
        self.ivme_y_egrisi = self.ivme_y_grafik_widget.plot(self.ivme_y_x, self.ivme_y_y, pen=pg.mkPen('y', width=2), name="İvme Y")
        self.ivme_z_egrisi = self.ivme_z_grafik_widget.plot(self.ivme_z_x, self.ivme_z_y, pen=pg.mkPen('k', width=2), name="İvme Z")

        self.timer = QTimer()
        self.timer.timeout.connect(self.grafik_guncelle_pyqtgraph)
        self.timer.start(200)

    def grafigi_ayarla(self, grafik_widget, y_etiketi, x_etiketi, baslik, renk):
        grafik_widget.setBackground('w')
        grafik_widget.setLabel('left', y_etiketi)
        grafik_widget.setLabel('bottom', x_etiketi)
        grafik_widget.setTitle(baslik)
        grafik_widget.showGrid(x=True, y=True)
        grafik_widget.addLegend()

    def grafik_guncelle_pyqtgraph(self):
        if self.ana_pencere and hasattr(self.ana_pencere, 'gyroXLineEdit'):
            try:
                irtifa = float(self.ana_pencere.irtifaLineEdit.text()) if self.ana_pencere.irtifaLineEdit.text() else None
                gyro_x = float(self.ana_pencere.gyroXLineEdit.text()) if self.ana_pencere.gyroXLineEdit.text() else None
                gyro_y = float(self.ana_pencere.gyroYLineEdit.text()) if self.ana_pencere.gyroYLineEdit.text() else None
                gyro_z = float(self.ana_pencere.gyroZLineEdit.text()) if self.ana_pencere.gyroZLineEdit.text() else None
                ivme_x = float(self.ana_pencere.ivmeXLineEdit.text()) if self.ana_pencere.ivmeXLineEdit.text() else None
                ivme_y = float(self.ana_pencere.ivmeYLineEdit.text()) if self.ana_pencere.ivmeYLineEdit.text() else None
                ivme_z = float(self.ana_pencere.ivmeZLineEdit.text()) if self.ana_pencere.ivmeZLineEdit.text() else None

                self.veri_ekle_ve_guncelle(self.irtifa_x, self.irtifa_y, self.irtifa_egrisi, irtifa)
                self.veri_ekle_ve_guncelle(self.gyro_x_x, self.gyro_x_y, self.gyro_x_egrisi, gyro_x)
                self.veri_ekle_ve_guncelle(self.gyro_y_x, self.gyro_y_y, self.gyro_y_egrisi, gyro_y)
                self.veri_ekle_ve_guncelle(self.gyro_z_x, self.gyro_z_y, self.gyro_z_egrisi, gyro_z)
                self.veri_ekle_ve_guncelle(self.ivme_x_x, self.ivme_x_y, self.ivme_x_egrisi, ivme_x)
                self.veri_ekle_ve_guncelle(self.ivme_y_x, self.ivme_y_y, self.ivme_y_egrisi, ivme_y)
                self.veri_ekle_ve_guncelle(self.ivme_z_x, self.ivme_z_y, self.ivme_z_egrisi, ivme_z)

            except ValueError:
                print("Uyarı: Geçersiz sayısal veri. Grafik güncellenmedi.")

    def veri_ekle_ve_guncelle(self, x_verisi, y_verisi, egri, yeni_veri):
        if yeni_veri is not None:
            y_verisi.append(yeni_veri)
            x_verisi.append(len(x_verisi))
            if len(x_verisi) > self.max_pencere:
                x_verisi = x_verisi[-self.max_pencere:]
                y_verisi = y_verisi[-self.max_pencere:]
            egri.setData(x_verisi, y_verisi)

    def logo_goster_grafik(self):
        try:
            pixmap = QPixmap(LOGO_MADRA).scaled(250, 250, Qt.KeepAspectRatio)
            if hasattr(self, 'grafikLogo'):
                self.grafikLogo.setPixmap(pixmap)
        except Exception as e:
            print(f"Grafik ekranı logo yüklenirken hata: {e}")

    def closeEvent(self, event):
        self.timer.stop()
        print("Grafik ekranı kapatıldı.")
        event.accept()


class gpss_ekrani(QWidget):
    def __init__(self, parent=None):
        super().__init__()
        self.ana_ekran = parent
        uic.loadUi(UI_GPS_EKRAN, self)
        self.setWindowTitle("Çift Harita Takip")
        self.logo_goster()
        self.gps_roket_enlem.setText(self.ana_ekran.roketGPSEnlemLineEdit.text())
        self.gps_roket_boylam.setText(self.ana_ekran.roketGPSBoylamLineEdit.text())
        self.gps_payload_enlem.setText(self.ana_ekran.payloadGPSEnlemLineEdit.text())
        self.gps_payload_boylam.setText(self.ana_ekran.payloadGPSBoylamLineEdit.text())
        # Roket harita alanı
        placeholder_roket = self.findChild(QWidget, "gps_roket")
        self.roketMap = QWebEngineView(self)
        self.roketMap.setGeometry(placeholder_roket.geometry())
        self.roketMap.show()
        placeholder_roket.deleteLater()
        self.roketMap.load(QUrl.fromLocalFile(os.path.abspath("harita_roket.html")))

        # Payload harita alanı
        placeholder_payload = self.findChild(QWidget, "gps_payload")
        self.payloadMap = QWebEngineView(self)
        self.payloadMap.setGeometry(placeholder_payload.geometry())
        self.payloadMap.show()
        placeholder_payload.deleteLater()
        self.payloadMap.load(QUrl.fromLocalFile(os.path.abspath("harita_payload.html")))

        # Timer başlat
        self.timer = QTimer()
        self.timer.timeout.connect(self.haritalari_guncelle)
        self.timer.start(500)
    def logo_goster(self):
        try:
            pixmap_giris = QPixmap(LOGO_MADRA).scaled(250, 250, Qt.KeepAspectRatio)
            if hasattr(self, 'gpssLogo'): self.gpssLogo.setPixmap(pixmap_giris)
        except Exception as e: print(f"gpss ekranı logo yüklenirken hata: {e}")
    
    def haritalari_guncelle(self):
        try:
            # Roket konumu
            lat_r = float(self.gps_roket_enlem.text())
            lon_r = float(self.gps_roket_boylam.text())
            js_roket = f"updateMarker({lat_r}, {lon_r});"
            self.roketMap.page().runJavaScript(js_roket)

            # Payload konumu
            lat_p = float(self.gps_payload_enlem.text())
            lon_p = float(self.gps_payload_boylam.text())
            js_payload = f"updateMarker({lat_p}, {lon_p});"
            self.payloadMap.page().runJavaScript(js_payload)

        except ValueError:
            pass  # Geçersiz sayılar varsa atla

class girisEkrani(QWidget):
    def __init__(self):
        super().__init__()
        try: uic.loadUi(UI_GIRIS_EKRANI, self)
        except Exception as e: print(f"Giriş Ekranı UI yüklenirken hata: {e}"); app.exit(1)
        self.logoshow_giris(); self.setWindowTitle("Giris/Kayit")
        self.kayit_penceresi_ref = None
        self.kayitGirisButton.clicked.connect(self.kayit_ekranini_goster)
        self.girisButton.clicked.connect(self.kullanici_girisi_kontrol_et)

    def logoshow_giris(self):
        try:
            pixmap_giris = QPixmap(LOGO_MADRA).scaled(100, 100, Qt.KeepAspectRatio)
            if hasattr(self, 'logolabelGiris'): self.logolabelGiris.setPixmap(pixmap_giris)
        except Exception as e: print(f"Giriş ekranı logo yüklenirken hata: {e}")

    def kullanici_girisi_kontrol_et(self):
        isim, sifre = self.kulNameText.text(), self.passwordText.text()
        if not isim or not sifre: QMessageBox.warning(self, "Eksik Bilgi", "Kullanıcı adı ve şifre boş olamaz."); return
        conn = baglanti_olustur()
        if conn:
            try:
                cursor = conn.cursor()
                cursor.execute("SELECT sifre FROM admin_verileri WHERE kullanici_adi = ?", (isim,))
                kayitli_hash = cursor.fetchone()
                if kayitli_hash and sifre_hashle(sifre) == kayitli_hash[0]:
                    self.ana_pencere = Pencere(); self.ana_pencere.show(); self.hide()
                else: QMessageBox.warning(self, "Hata", "Geçersiz kullanıcı adı veya şifre.")
            except sqlite3.Error as e: QMessageBox.critical(self, "Veritabanı Hatası", f"Giriş kontrolü hatası: {e}")
            finally: conn.close()
        else: QMessageBox.critical(self, "Veritabanı Hatası", "Veritabanına bağlanılamadı.")

    def kayit_ekranini_goster(self):
        if self.kayit_penceresi_ref is None or not self.kayit_penceresi_ref.isVisible():
             self.kayit_penceresi_ref = kayitEkrani(self)
        self.kayit_penceresi_ref.show(); self.hide()


class kayitEkrani(QWidget):
    def __init__(self, giris_ekrani_ref=None):
        super().__init__()
        self.giris_ekrani_referansi = giris_ekrani_ref
        try: uic.loadUi(UI_KAYIT_EKRANI, self)
        except Exception as e: print(f"Kayıt Ekranı UI yüklenirken hata: {e}"); app.exit(1)
        self.setWindowTitle("Kayıt Ekranı"); self.logoshow_kayit()
        self.kayit_girisEkranButton.clicked.connect(self.giris_ekranini_goster_ve_kapat)
        self.kayitButton.clicked.connect(self.kayit_ol)

    def logoshow_kayit(self):
        try:
            pixmap_kayit = QPixmap(LOGO_MADRA).scaled(100, 100, Qt.KeepAspectRatio)
            if hasattr(self, 'logolabelKayit'): self.logolabelKayit.setPixmap(pixmap_kayit)
        except Exception as e: print(f"Kayıt ekranı logo yüklenirken hata: {e}")

    def kayit_ol(self):
        ref, isim = self.refText.toPlainText(), self.yeniKulNameText.toPlainText()
        sifre, sifre_tkr = self.yeniPasswordText.toPlainText(), self.passwordTekrarText.toPlainText()
        if not all([ref, isim, sifre, sifre_tkr]): QMessageBox.warning(self, "Eksik Bilgi", "Tüm alanlar dolu olmalı."); return
        if ref == "ROCKET":
            if sifre == sifre_tkr:
                conn = baglanti_olustur()
                if conn:
                    try:
                        cursor = conn.cursor()
                        cursor.execute("INSERT INTO admin_verileri (kullanici_adi, sifre) VALUES (?, ?)",
                                       (isim, sifre_hashle(sifre)))
                        conn.commit()
                        QMessageBox.information(self, "Kayıt Başarılı", f"{isim} başarıyla kaydedildi.")
                        self.giris_ekranini_goster_ve_kapat()
                    except sqlite3.IntegrityError: QMessageBox.warning(self, "Hata", f"'{isim}' kullanıcı adı zaten mevcut.")
                    except sqlite3.Error as e: QMessageBox.critical(self, "Veritabanı Hatası", f"Kayıt hatası: {e}")
                    finally: conn.close()
            else: QMessageBox.warning(self, "Hata", "Şifreler eşleşmiyor.")
        else: QMessageBox.warning(self, "Hata", "Geçersiz Referans Kodu.")

    def giris_ekranini_goster_ve_kapat(self):
        if self.giris_ekrani_referansi: self.giris_ekrani_referansi.show()
        else: self.fallback_giris = girisEkrani(); self.fallback_giris.show(); print("Uyarı: Kayıt için giriş ref. yok.")
        self.close()

if __name__ == "__main__":
    app = QApplication(sys.argv)
    tablo_olustur()         # Admin verileri için
    ucus_tablosu_olustur()  # Uçuş verileri için
    girisekrani_ana = girisEkrani()
    girisekrani_ana.show()
    sys.exit(app.exec_())