import socket
import threading
import os
import time
from queue import Queue

VERSION = "S.T.C.S. v0.1.1-Alpha(Test) , Github: https://github.com/Darkfoxy5/S.T.C.S. "
HOST = '0.0.0.0'
PORT = 5555

SERVER_PASSWORD = "Şifreyi buraya yaz"
RULES = "Kuralları buraya yaz"

clients = []
nicknames = []
client_ips = []
banned_ips = set()
lock = threading.Lock()
BANNED_FILE = "banned_ips.txt"

# Spam  kontrolü
message_counts = {}

# Banlı IP'leri yükle
try:
    if os.path.exists(BANNED_FILE):
        with open(BANNED_FILE, "r") as f:
            for line in f:
                banned_ips.add(line.strip())
    print("Ban sistemi aktif!")
except Exception as e:
    print(f"Ban sistemi başlatılamadı: {e}")

# Ban IP kayıtları
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
    broadcast_queue = Queue()

    def broadcast_worker():
        while True:
            message, sender = broadcast_queue.get()
            disconnected_clients = []
            with lock:
                for c in clients[:]:
                    if c != sender:
                        try:
                            c.send(message.encode('utf-8'))
                        except (ConnectionResetError, OSError):
                            try:
                                idx = clients.index(c)
                                disconnected_clients.append(idx)
                            except ValueError:
                                continue
                for idx in sorted(disconnected_clients, reverse=True):
                    removed_nick = nicknames.pop(idx)
                    clients.pop(idx)
                    client_ips.pop(idx)
                    print(f"{removed_nick} broadcast sırasında listeden çıkarıldı.")
            broadcast_queue.task_done()

    def broadcast(message, sender=None):
        broadcast_queue.put((message, sender))

    threading.Thread(target=broadcast_worker, daemon=True).start()
    print("Broadcast sistemi aktif!")
except Exception as e:
    print(f"Broadcast sistemi başlatılamadı: {e}")

def remove_client(client, nickname):
    with lock:
        if client in clients:
            idx = clients.index(client)
            clients.pop(idx)
            nicknames.pop(idx)
            client_ips.pop(idx)
    try:
        client.close()
    except:
        pass
    broadcast(f"{nickname} ayrıldı!\n", None)
    print(f"{nickname} ayrıldı.")

def handle(client, nickname, ip):
    time_window = 10
    message_limit = 11

    while True:
        try:
            raw = client.recv(1024)
            if not raw:
                break
            if len(raw) > 1024:
                client.send("Mesaj çok uzun!\n".encode('utf-8'))
                continue

            msg = raw.decode('utf-8', errors='replace').strip()
            if not msg:
                break

            # Spam  kontrolü
            current_time = time.time()
            last_time, count = message_counts.get(nickname, (current_time, 0))
            if current_time - last_time <= time_window:
                count += 1
            else:
                count = 1
                last_time = current_time
            message_counts[nickname] = (last_time, count)

            if count > message_limit:
                client.send("Flood tespit edildi, bağlantınız kesiliyor!\n".encode('utf-8'))
                remove_client(client, nickname)
                break

            # Komutlar
            if msg.startswith("/"):
                parts = msg.split(" ", 2)
                cmd = parts[0].lower()
                if cmd == "/list":
                    with lock:
                        user_list = ", ".join(nicknames)
                    client.send(f"Bağlı kullanıcılar: {user_list}\n".encode('utf-8'))
                elif cmd == "/v":
                    client.send(f"Sunucu sürümü: {VERSION}\n".encode('utf-8'))
                elif cmd == "/pm" and len(parts) == 3:
                    target_name = parts[1]
                    private_msg = parts[2]
                    with lock:
                        target_client = None
                        if target_name in nicknames:
                            target_client = clients[nicknames.index(target_name)]
                    if target_client:
                        try:
                            target_client.send(f"[Özel] {nickname}: {private_msg}".encode('utf-8'))
                            client.send(f"[Özel] {nickname} -> {target_name}: {private_msg}".encode('utf-8'))
                        except:
                            client.send(f"Kullanıcı {target_name} bağlantıda değil.\n".encode('utf-8'))
                    else:
                        client.send(f"Kullanıcı {target_name} bulunamadı.\n".encode('utf-8'))
                else:
                    client.send("Bilinmeyen komut veya yetkisiz.\n".encode('utf-8'))
            else:
                full_message = f"{nickname}: {msg}"
                print(full_message)
                broadcast(full_message, client)

        except socket.timeout:
            client.send("15 dakika boyunca işlem yapmadığınız için bağlantınız kesildi.\n".encode('utf-8'))
            remove_client(client, nickname)
            print(f"{nickname} zaman aşımı nedeniyle bağlantı kesildi.")
            break
        except Exception as e:
            print(f"{nickname} bağlantısı beklenmedik şekilde kesildi: {e}")
            remove_client(client, nickname)
            break

def receive():
    server.listen()
    print(f"Sunucu {HOST}:{PORT} adresinde çalışıyor...")
    while True:
        try:
            client, address = server.accept()
            client.settimeout(900)
        except socket.timeout:
            print("Bir istemci zaman aşımı nedeniyle düşürüldü.")
            continue
        except (OSError, ConnectionResetError) as e:
            print(f"Sunucu kabul sırasında bağlantı hatası: {e}")
            continue

        ip = address[0]

        if ip in banned_ips:
            client.send("Bu IP yasaklı!\n".encode('utf-8'))
            client.close()
            continue

        if ip in client_ips:
            client.send("Bu IP zaten bağlı! Birden fazla oturum açamazsınız.\n".encode('utf-8'))
            with lock:
                indices_to_remove = [i for i, x in enumerate(client_ips) if x == ip]
                for idx in reversed(indices_to_remove):
                    try:
                        clients[idx].close()
                    except:
                        pass
                    clients.pop(idx)
                    nicknames.pop(idx)
                    client_ips.pop(idx)
            continue

        # Şifre kontrolü
        raw_pass = client.recv(1024)
        if not raw_pass:
            client.close()
            continue
        password = raw_pass.decode('utf-8', errors='replace').strip()
        if password != SERVER_PASSWORD:
            client.send("Hatalı şifre!\n".encode('utf-8'))
            client.close()
            continue

        # Ad sorulması  
        client.send("Lütfen adınızı girin: ".encode('utf-8'))
        raw_nick = client.recv(1024)
        if not raw_nick:
            client.close()
            continue
        nickname = raw_nick.decode('utf-8', errors='replace').strip()
        nickname = "_".join(nickname.split())
        if not nickname:
            nickname = "Anonim"

        if nickname in nicknames:
            client.send("Bu takma ad zaten kullanılıyor.\n".encode('utf-8'))
            client.close()
            continue

        with lock:
            clients.append(client)
            nicknames.append(nickname)
            client_ips.append(ip)

        print(f"{ip} bağlandı. Takma ad: {nickname}")
        broadcast(f"{nickname} sohbete katıldı!\n", client)
        client.send("Sohbete hoş geldin!\n".encode('utf-8'))
        client.send(f"Sunucu sürümü: {VERSION}\n".encode('utf-8'))
        client.send(f"Kurallar/Rules: {RULES}\n".encode('utf-8'))

        thread = threading.Thread(target=handle, args=(client, nickname, ip), daemon=True)
        thread.start()

def server_commands():
    while True:
        cmd = input()
        parts = cmd.split(" ", 2)
        command = parts[0].lower()

        if command == "/help":
            help_text = (
                "Sunucu terminali için kullanılabilir komutlar:(31.08.2025)\n"
                "/shutdown -> Sunucuyu kapatır\n"
                "/v -> Bulunduğunuz sunucunun versiyonunu Gösterir\n"
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
            with lock:
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
                kicked_client.send("Sunucudan atıldınız.\n".encode('utf-8'))
                remove_client(kicked_client, kick_name)
                broadcast(f"{kick_name} sunucudan atıldı!\n")
                print(f"{kick_name} atıldı.")
            else:
                print(f"Kullanıcı {kick_name} bulunamadı.")

        elif command == "/ban" and len(parts) >= 2:
            ban_name = parts[1]
            if ban_name in nicknames:
                idx = nicknames.index(ban_name)
                ip = client_ips[idx]
                with lock:
                    banned_ips.add(ip)
                    save_banned_ips()
                clients[idx].send("Banlandınız!\n".encode('utf-8'))
                remove_client(clients[idx], ban_name)
                broadcast(f"{ban_name} yasaklandı!\n")
                print(f"{ban_name} banlandı (IP: {ip}).")
            else:
                print(f"Kullanıcı {ban_name} bulunamadı.")

        elif command == "/unban" and len(parts) >= 2:
            ip = parts[1]
            if ip in banned_ips:
                with lock:
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
            with lock:
                user_list = ", ".join(nicknames)
            print(f"Bağlı kullanıcılar: {user_list}")

        elif command == "/v":
            print(f"Sunucu sürümü: {VERSION}")      

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
