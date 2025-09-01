import socket
import threading
import os
import time
from queue import Queue, Full

broadcast_queue = Queue(maxsize=2000)

VERSION = "S.T.C.S. v0.1.1-Alpha(Test) , Github: https://github.com/Darkfoxy5/S.T.C.S. "
HOST = '0.0.0.0'
PORT = 5555

SERVER_PASSWORD = "12345" #Şifreyi buraya yaz, "12345" varsayılan halka açık sunucu şifresidir.
RULES = "Kuralları buraya yaz"

clients = []
nicknames = []
client_ips = []
banned_ips = set()
lock = threading.Lock()
BANNED_FILE = "banned_ips.txt"

# Spam kontrolü
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
    def broadcast_worker():
        while True:
            message, sender = broadcast_queue.get()
            disconnected_clients = []
            with lock:
                for c in clients[:]:
                    if c != sender:
                        try:
                            c.send(message.encode('utf-8'))
                        except (socket.error, ConnectionResetError, OSError) as e:
                            try:
                                idx = clients.index(c)
                                disconnected_clients.append(idx)
                                try:
                                    c.close()
                                except:
                                    pass
                            except ValueError:
                                continue

                for idx in sorted(disconnected_clients, reverse=True):
                    try:
                        removed_nick = nicknames.pop(idx)
                    except IndexError:
                        removed_nick = None
                    try:
                        clients.pop(idx)
                    except IndexError:
                        pass
                    try:
                        client_ips.pop(idx)
                    except IndexError:
                        pass
                    if removed_nick:
                        message_counts.pop(removed_nick, None)
                        print(f"{removed_nick} broadcast sırasında listeden çıkarıldı.")
            broadcast_queue.task_done()

    def broadcast(message, sender=None):
        try:
            broadcast_queue.put_nowait((message, sender))
        except Full:
            pass

    threading.Thread(target=broadcast_worker, daemon=True).start()
    print("Broadcast sistemi aktif!")
except Exception as e:
    print(f"Broadcast sistemi başlatılamadı: {e}")

# client temizleme
def remove_client(client, nickname):
    with lock:
        if client in clients:
            try:
                idx = clients.index(client)
            except ValueError:
                idx = None
            if idx is not None:
                try:
                    clients.pop(idx)
                except:
                    pass
                try:
                    nicknames.pop(idx)
                except:
                    pass
                try:
                    client_ips.pop(idx)
                except:
                    pass
        message_counts.pop(nickname, None)

    try:
        client.close()
    except:
        pass

    broadcast(f"{nickname} ayrıldı!\n", None)
    print(f"{nickname} ayrıldı.")

def handle(client, nickname, ip):
    # saniye başı mesaj limiti
    time_window = 10
    message_limit = 12

    while True:
        try:
            raw = client.recv(1024)
            if not raw:
                break

            if len(raw) > 1024:
                try:
                    client.send("Mesaj çok uzun!\n".encode('utf-8'))
                except:
                    pass
                continue

            msg = raw.decode('utf-8', errors='replace').strip()
            if not msg:
                break

            # Spam kontrolü
            current_time = time.time()
            last_time, count = message_counts.get(nickname, (current_time, 0))
            if current_time - last_time <= time_window:
                count += 1
            else:
                count = 1
                last_time = current_time
            message_counts[nickname] = (last_time, count)

            if count > message_limit:
                try:
                    client.send("Flood tespit edildi, bağlantınız kesiliyor!\n".encode('utf-8'))
                except:
                    pass
                remove_client(client, nickname)
                break

            # Komutlar
            if msg.startswith("/"):
                parts = msg.split(" ", 2)
                cmd = parts[0].lower()

                if cmd == "/list":
                    with lock:
                        user_list = ", ".join(nicknames)
                    try:
                        client.send(f"Bağlı kullanıcılar: {user_list}\n".encode('utf-8'))
                    except:
                        pass

                elif cmd == "/v":
                    try:
                        client.send(f"Sunucu sürümü: {VERSION}\n".encode('utf-8'))
                    except:
                        pass

                elif cmd == "/pm" and len(parts) == 3:
                    target_name = parts[1]
                    private_msg = parts[2]
                    with lock:
                        target_client = None
                        if target_name in nicknames:
                            try:
                                target_client = clients[nicknames.index(target_name)]
                            except (ValueError, IndexError):
                                target_client = None

                    if target_client:
                        try:
                            target_client.send(f"[Özel] {nickname}: {private_msg}".encode('utf-8'))
                            client.send(f"[Özel] {nickname} -> {target_name}: {private_msg}".encode('utf-8'))
                        except:
                            try:
                                client.send(f"Kullanıcı {target_name} bağlantıda değil.\n".encode('utf-8'))
                            except:
                                pass
                    else:
                        try:
                            client.send(f"Kullanıcı {target_name} bulunamadı.\n".encode('utf-8'))
                        except:
                            pass

                else:
                    try:
                        client.send("Bilinmeyen komut veya yetkisiz.\n".encode('utf-8'))
                    except:
                        pass
            else:
                # mesaj
                full_message = f"{nickname}: {msg}"
                print(full_message)
                broadcast(full_message, client)

        except (ConnectionResetError, OSError) as e:
            print(f"{nickname} bağlantısı aniden kesildi: {e}.")
            remove_client(client, nickname)
            break

        except socket.timeout:
            try:
                client.send("15 dakika boyunca işlem yapmadığınız için bağlantınız kesildi.\n".encode('utf-8'))
            except:
                pass
            remove_client(client, nickname)
            print(f"{nickname} zaman aşımı nedeniyle bağlantı kesildi.")
            break

        except Exception as e:
            print(f"{nickname} bağlantısı beklenmedik şekilde kesildi: {e}")
            remove_client(client, nickname)
            break

def receive():
    server.listen(100)
    print(f"Sunucu {HOST}:{PORT} adresinde çalışıyor...")
    while True:
        try:
            client, address = server.accept()
            client.settimeout(900)
        except socket.timeout:
            print("Bir istemci zaman aşımı nedeniyle düşürüldü.")
            continue
        except (socket.error, OSError, ConnectionResetError) as e:
            print(f"Sunucu kabul sırasında bağlantı hatası: {e}")
            continue

        ip = address[0]

        # Ban kontrolü
        if ip in banned_ips:
            try:
                client.send("Bu IP yasaklı!\n".encode('utf-8'))
            except:
                pass
            try:
                client.close()
            except:
                pass
            continue

        if ip in client_ips:
            try:
                client.send("Bu IP zaten bağlı! Birden fazla oturum açamazsınız.\n".encode('utf-8'))
            except:
                pass
            with lock:
                indices_to_remove = [i for i, x in enumerate(client_ips) if x == ip]
                for idx in reversed(indices_to_remove):
                    try:
                        clients[idx].close()
                    except:
                        pass
                    try:
                        clients.pop(idx)
                    except:
                        pass
                    try:
                        nicknames.pop(idx)
                    except:
                        pass
                    try:
                        client_ips.pop(idx)
                    except:
                        pass
            try:
                client.close()
            except:
                pass
            continue

        # Şifre kontrolü
        try:
            raw_pass = client.recv(1024)
        except (ConnectionResetError, OSError):
            try:
                client.close()
            except:
                pass
            continue
        if not raw_pass:
            try:
                client.close()
            except:
                pass
            continue
        password = raw_pass.decode('utf-8', errors='replace').strip()
        if password != SERVER_PASSWORD:
            try:
                client.send("Hatalı şifre!\n".encode('utf-8'))
            except:
                pass
            try:
                client.close()
            except:
                pass
            continue

        # Ad sorulması
        try:
            client.send("Lütfen adınızı girin: ".encode('utf-8'))
            raw_nick = client.recv(1024)
        except (ConnectionResetError, OSError):
            try:
                client.close()
            except:
                pass
            continue
        if not raw_nick:
            try:
                client.close()
            except:
                pass
            continue
        nickname = raw_nick.decode('utf-8', errors='replace').strip()
        nickname = "_".join(nickname.split())
        if not nickname:
            nickname = "Anonim"

        if nickname in nicknames:
            try:
                client.send("Bu takma ad zaten kullanılıyor.\n".encode('utf-8'))
            except:
                pass
            try:
                client.close()
            except:
                pass
            continue

        with lock:
            clients.append(client)
            nicknames.append(nickname)
            client_ips.append(ip)

        print(f"{ip} bağlandı. Takma ad: {nickname}")
        broadcast(f"{nickname} sohbete katıldı!\n", client)
        try:
            client.send("Sohbete hoş geldin!\n".encode('utf-8'))
            client.send(f"Sunucu sürümü: {VERSION}\n".encode('utf-8'))
            client.send(f"Kurallar/Rules: {RULES}\n".encode('utf-8'))
        except:
            remove_client(client, nickname)
            continue

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
                try:
                    kicked_client.send("Sunucudan atıldınız.\n".encode('utf-8'))
                except:
                    pass
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
                try:
                    clients[idx].send("Banlandınız!\n".encode('utf-8'))
                except:
                    pass
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

# Socket oluşturma ve başlatma
try:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    try:
        server.setsockopt(socket.SOL_SOCKET, socket.SO_KEEPALIVE, 1)
    except:
        pass
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
except KeyboardInterrupt:
    print("\nSunucu manuel olarak kapatılıyor...")
    os._exit(0)
except Exception as e:
    print(f"Bağlantı dinleme başlatılamadı: {e}")

