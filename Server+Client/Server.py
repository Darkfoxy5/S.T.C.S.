import socket
import threading
import os

VERSION = "v0.1.0-Alpha"
HOST = '0.0.0.0'
PORT = 5555

# Sunucu şifresi sunucuya girilirken sorulur.
SERVER_PASSWORD = "Şifreyi buraya yaz"

clients = []
nicknames = []
client_ips = []
banned_ips = set()
BANNED_FILE = "banned_ips.txt"

# Banlı IP'leri yükle
try:
    if os.path.exists(BANNED_FILE):
        with open(BANNED_FILE, "r") as f:
            for line in f:
                banned_ips.add(line.strip())
    print("Ban sistemi aktif!")
except Exception as e:
    print(f"Ban sistemi başlatılamadı: {e}")

#Ban IP kayıtları
try:
    def save_banned_ips():
        with open(BANNED_FILE, "w") as f:
            for ip in banned_ips:
                f.write(ip + "\n")
    print("Ban kaydetme sistemi aktif!")
except Exception as e:
    print(f"Ban kaydetme sistemi başlatılamadı: {e}")

# Broadcast sistemi
try:
    def broadcast(message, sender=None):
        for c in clients:
            if c != sender:
                try:
                    c.send(message.encode('utf-8'))
                except:
                    pass
    print("Broadcast sistemi aktif!")
except Exception as e:
    print(f"Broadcast sistemi başlatılamadı: {e}")

try:
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

                    elif cmd == "/v":
                        client.send(f"Sunucu sürümü: {VERSION}\n".encode('utf-8'))
  

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
                    full_message = f"{nickname}: {msg}"
                    print(full_message)
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
    print("Handle sistemi aktif!")
except Exception as e:
    print(f"Handle sistemi başlatılamadı: {e}")

#Giriş denetimi
try:
    def receive():
        server.listen()
        print(f"Sunucu {HOST}:{PORT} adresinde çalışıyor...")
        while True:
            try:
                client, address = server.accept()
            except OSError:
                print(f"Sunucu dinleme kapandı: {OSError}")
                break

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
            client.send(f"Sunucu sürümü: {VERSION}\n".encode('utf-8'))

            thread = threading.Thread(target=handle, args=(client, nickname, ip), daemon=True)
            thread.start()
    print("Giriş Denetim Sistemi başlatıldı!")   
except Exception as e:
    print(f"Giriş Denetim Sisteni başlatılamadı: {e}")           

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
             try:
                 c.close()
             except:
                 pass
            try:
                 server.close()
            except:
                pass
            print("Sunucu kapatıldı.")
            import os; os._exit(0)

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
            message = " ".join(parts[1:])
            broadcast(f"[Sunucu]: {message}\n")
            print(f"[Sunucu]: {message}")

        elif command == "/list":
            print(f"Bağlı kullanıcılar: {', '.join(nicknames)}")

try:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    print("Sunucu soketi aktif!")
except Exception as e:
    print(f"Sunucu soketi başlatılamadı: {e}")

try:
    threading.Thread(target=server_commands, daemon=True).start()
    print("Sunucu komut sistemi aktif!")
except Exception as e:
    print(f"Komut sistemi başlatılamadı: {e}")

try:
    print("Bağlantı dinleme başlatılıyor...")
    receive()
except Exception as e:
    print(f"Bağlantı dinleme başlatılamadı: {e}")
