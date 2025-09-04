import socket
import threading
import getpass
import sys
import urllib.request
import os

URL = "https://raw.githubusercontent.com/Darkfoxy5/S.T.C.S./refs/heads/main/Public_Server_list"

def get_latest_server_list():
    try:
        with urllib.request.urlopen(URL) as response:
            content = response.read().decode('utf-8')
            return content.splitlines()
    except Exception as e:
        print(f"Server Dosyası alınamadı/Server file could not be retrieved: {e}")
        return []
servers = get_latest_server_list()
for s in servers:
    print(s)

PORT = 5555
SERVER_IP = input("IP address: ")

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((SERVER_IP, PORT))

# Sanüsrlü Şifre
password = getpass.getpass("Şifre/Password(Herkese açık/Public Servers: 12345): ")
client.send(password.encode('utf-8'))

def receive():
    while True:
        try:
            message = client.recv(1024).decode('utf-8', errors='replace')
            if not message:
                break

            if message.strip() == "[Sunucu/Server]:CLEAR":
                os.system('cls' if sys.platform == 'win32' else 'clear')
                print("[Sistem/System]: Sohbet temizlendi/The chat has been deleted.")
                continue

            print(message)
        except:
            print("Bağlantı kesildi/Connection lost!")
            client.close()
            break

def write():
    while True:
        try:
            message = input("")
            if message == "/yardım":
                print("Kullanılabilir komutlar:(31.08.2025)")
                print("/help -> Displays the English Help menu!")
                print("/list -> Bağlı kullanıcıları gösterir")
                print("/clear -> Sohbetini temizler")
                print("/pm <kullanıcı> <mesaj> -> Özel mesaj gönderir")
                print("/v -> Bulunduğunuz sunucunun versiyonunu Gösterir")
                print("/quit -> Güvenli bir şekilde sunucudan çıkmanızı şağlar")
                print("/yardım -> Yardım menüsünü gösterir")
            if message == "/help":
                print("Available commands:(31.08.2025)")
                print("/yardım -> Türkçe Yardım menüsünü gösterir!")
                print("/list -> Shows connected users")
                print("/clear -> Cleans your chat")
                print("/pm <user> <message> -> Send a private message")
                print("/v -> Displays the server version")
                print("/quit -> Ensures you exit the server safely")
                print("/help -> Displays the help menu")
            if message.strip() == "/clear":
                os.system('cls' if sys.platform == 'win32' else 'clear')
                print("[Sistem/System]: Sohbet temizlendi/The chat has been deleted.(lokal/local).")
                continue
            if message == "/quit":
                try:
                    client.shutdown(socket.SHUT_RDWR)
                except:
                     pass
                try:
                    client.close()
                except:
                    pass
                sys.exit(0)
            else:
                client.send(message.encode('utf-8'))
        except:
            print("Mesaj gönderilemedi/Message failed to send.!")
            client.close()
            break

threading.Thread(target=receive).start()
threading.Thread(target=write).start()
