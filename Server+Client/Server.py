import socket
import threading
from datetime import datetime
import os

HOST = '0.0.0.0'
PORT = 5555

# Sunucu şifresi sunucuya girilirken sorulur.
SERVER_PASSWORD = "Şifreyi buraya yaz" 

clients = []
nicknames = []
client_ips = []
banned_ips = set()
LOG_FILE = "log.txt"
BANNED_FILE = "banned_ips.txt"

# Banlı IP'leri yükle
if os.path.exists(BANNED_FILE):
    with open(BANNED_FILE, "r") as f:
        for line in f:
            banned_ips.add(line.strip())

# Log kaydı
def log_message(message):
    with open(LOG_FILE, "a", encoding="utf-8") as f:
        f.write(message + "\n")

def save_banned_ips():
    with open(BANNED_FILE, "w") as f:
        for ip in banned_ips:
            f.write(ip + "\n")

# Mesajların alımı/gönderimi ve kulanıcı komutları
def broadcast(message, sender=None):
    for c in clients:
        if c != sender:
            try:
                c.send(message.encode('utf-8'))
            except:
                pass

def handle(client, nickname, ip):
    while True:
        try:
            msg = client.recv(1024).decode('utf-8').strip()
            if not msg:
                continue

            if msg.startswith("/"):
                parts = msg.split(" ", 2)
                cmd = parts[0].lower()

                if cmd == "/list":
                    user_list = ", ".join(nicknames)
                    client.send(f"Bağlı kullanıcılar: {user_list}\n".encode('utf-8'))

                elif cmd == "/pm" and len(parts) == 3:
                    target_name = parts[1]
                    private_msg = parts[2]
                    if target_name in nicknames:
                        target_index = nicknames.index(target_name)
                        target_client = clients[target_index]
                        target_client.send(f"[Özel] {nickname}: {private_msg}".encode('utf-8'))
                        client.send(f"[Özel] {nickname} -> {target_name}: {private_msg}".encode('utf-8'))
                    else:
                        client.send(f"Kullanıcı {target_name} bulunamadı.\n".encode('utf-8'))

                else:
                    client.send("Bilinmeyen komut veya yetkisiz.\n".encode('utf-8'))
        
            else:
                timestamp = datetime.now().strftime("%H:%M")
                full_message = f"[{timestamp}] {nickname}: {msg}"
                print(full_message)
                log_message(full_message)
                broadcast(full_message, client)

        except:
            break

    if client in clients:
        index = clients.index(client)
        clients.remove(client)
        client.close()
        nicknames.remove(nickname)
        client_ips.remove(ip)
        broadcast(f"{nickname} ayrıldı!\n", None)
        print(f"{nickname} ayrıldı.")
#Giriş denetimi
def receive():
    server.listen()
    print(f"Sunucu {HOST}:{PORT} adresinde çalışıyor...")
    while True:
        client, address = server.accept()
        ip = address[0]

        if ip in banned_ips:
            client.send("Bu IP yasaklı!\n".encode('utf-8'))
            client.close()
            continue

        if ip in client_ips:
            client.send("Bu IP zaten bağlı! Birden fazla oturum açamazsınız.\n".encode('utf-8'))
            client.close()
            continue

        # Şifre kontrolü
        password = client.recv(1024).decode('utf-8').strip()
        if password != SERVER_PASSWORD:
            client.send("Hatalı şifre!\n".encode('utf-8'))
            client.close()
            continue

        # Ad sorulması  
        client.send("Lütfen adınızı girin: ".encode('utf-8'))
        nickname = client.recv(1024).decode('utf-8').strip()
        if not nickname:
            nickname = "Anonim"

        if nickname in nicknames:
            client.send("Bu takma ad zaten kullanılıyor.\n".encode('utf-8'))
            client.close()
            continue

        clients.append(client)
        nicknames.append(nickname)
        client_ips.append(ip)

        print(f"{ip} bağlandı. Takma ad: {nickname}")
        broadcast(f"{nickname} sohbete katıldı!\n", client)
        client.send("Sohbete hoş geldin!\n".encode('utf-8'))

        thread = threading.Thread(target=handle, args=(client, nickname, ip))
        thread.start()
#Sunucuya özel  komutlar
def server_commands():
    while True:
        cmd = input()
        parts = cmd.split(" ", 2)
        command = parts[0].lower()

        if command == "/help":
            help_text = (
                "Sunucu terminali için kullanılabilir komutlar:\n"
                "/shutdown -> Sunucuyu kapatır\n"
                "/kick <kullanıcı> -> Belirtilen kullanıcıyı atar\n"
                "/ban <kullanıcı> -> Belirtilen kullanıcıyı IP ile banlar\n"
                "/unban <IP> -> Banlı IP'nin banını kaldırır\n"
                "/say <mesaj> -> Sunucu olarak sohbet penceresine mesaj gönderir\n"
                "/list -> Bağlı kullanıcıları listeler\n"
            )
            print(help_text)
            continue

        if command == "/shutdown":
            broadcast("Sunucu kapatılıyor...\n")
            for c in clients:
                c.close()
            server.close()
            print("Sunucu kapatıldı.")
            exit()

        elif command == "/kick" and len(parts) >= 2:
            kick_name = parts[1]
            if kick_name in nicknames:
                idx = nicknames.index(kick_name)
                kicked_client = clients[idx]
                ip = client_ips[idx]
                kicked_client.send("Sunucudan atıldınız.\n".encode('utf-8'))
                kicked_client.close()
                broadcast(f"{kick_name} sunucudan atıldı!\n")
                print(f"{kick_name} atıldı.")
            else:
                print(f"Kullanıcı {kick_name} bulunamadı.")

        elif command == "/ban" and len(parts) >= 2:
            ban_name = parts[1]
            if ban_name in nicknames:
                idx = nicknames.index(ban_name)
                ip = client_ips[idx]
                banned_ips.add(ip)
                save_banned_ips()
                clients[idx].send("Banlandınız!\n".encode('utf-8'))
                clients[idx].close()
                broadcast(f"{ban_name} yasaklandı!\n")
                print(f"{ban_name} banlandı (IP: {ip}).")
            else:
                print(f"Kullanıcı {ban_name} bulunamadı.")

        elif command == "/unban" and len(parts) >= 2:
            ip = parts[1]
            if ip in banned_ips:
                banned_ips.remove(ip)
                save_banned_ips()
                print(f"{ip} ban kaldırıldı.")
                broadcast(f"{ip} banı kaldırıldı!\n")
            else:
                print(f"{ip} banlı değil.")

        elif command == "/say" and len(parts) >= 2:
            message = parts[1]
            broadcast(f"[Sunucu]: {message}\n")
            print(f"[Sunucu]: {message}")

        elif command == "/list":
            print(f"Bağlı kullanıcılar: {', '.join(nicknames)}")


server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
server.bind((HOST, PORT))
threading.Thread(target=server_commands, daemon=True).start()
receive()

