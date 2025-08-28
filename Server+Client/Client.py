import socket
import threading
import getpass

PORT = 5555
SERVER_IP = input("Sunucu IP'sini gir: ")

client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
client.connect((SERVER_IP, PORT))

# Maskeli şifre (gizli giriş)
password = getpass.getpass("Sunucu şifresini gir: ")
client.send(password.encode('utf-8'))

def receive():
    while True:
        try:
            message = client.recv(1024).decode('utf-8')
            if not message:
                break
            print(message)
        except:
            print("Sunucuyla bağlantı kesildi!")
            client.close()
            break

def write():
    while True:
        try:
            message = input("")
            if message == "/help":
                print("Kullanılabilir komutlar:")
                print("/list -> Bağlı kullanıcıları gösterir")
                print("/pm <kullanıcı> <mesaj> -> Özel mesaj gönderir")
                print("/help -> Yardım menüsünü gösterir")
            else:
                client.send(message.encode('utf-8'))
        except:
            print("Mesaj gönderilemedi!")
            client.close()
            break

threading.Thread(target=receive).start()
threading.Thread(target=write).start()


