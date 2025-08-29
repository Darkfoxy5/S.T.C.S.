import socket
import threading
import os
import time
import re
import logging

# -------------------- Logging --------------------
logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")

# -------------------- Basic config --------------------
HOST = '0.0.0.0'
PORT = 5555

SERVER_PASSWORD = os.environ.get("SERVER_PASSWORD", "Şifreyi buraya yaz")

RECV_BUFFER = 4096         # daha büyük mesajları alabilmek için
LISTEN_BACKLOG = 100       # daha yüksek kulanıcı limiti
MAX_PER_IP = 5           # aynı IP için eşzamanlı bağlantı limiti

PING_INTERVAL = 10         # monitor thread kontrol sıklığı (saniye) - dev: 10s
PING_THRESHOLD = 60        # sessizlikten sonra PING at (saniye) - dev: 60s
PONG_TIMEOUT = 5           # PONG bekleme süresi (saniye) - dev: 5s
IDLE_LIMIT = 300           # tamamen pasifse kapat (saniye) - dev: 300s

# -------------------- Version check --------------------
GITHUB_RAW_URL = "https://raw.githubusercontent.com/Darkfoxy5/S.T.C.S./main/Server%2BClient/Server.py"
LOCAL_SERVER_PATH = "Server.py"
CHECK_FROM_LINE = 16
VERSION_CACHE_TTL = 60     # cache TTL: 60s - dev hızlı geri dönüş
VERSION_CACHE = {
    "time": 0,
    "result": None,
    "local_mtime": None,
    "url": None,
    "start_line": None
}

clients = []
nicknames = []
client_ips = []
banned_ips = set()
BANNED_FILE = "banned_ips.txt"
lock = threading.Lock()

last_activity = {}   
last_ping = {}       

# -------------------- Nickname regex --------------------
try:
    NICK_REGEX = re.compile(r"^[A-Za-zÇçĞğİıÖöŞşÜü0-9_\- ]{1,20}$")
    logging.info("Nickname regex aktif!")
except Exception as e:
    logging.error(f"Nickname regex,hata: {e}")

# -------------------- Ban yükle --------------------
try:
    if os.path.exists(BANNED_FILE):
        with open(BANNED_FILE, "r", encoding="utf-8", errors="replace") as f:
            for line in f:
                banned_ips.add(line.strip())
    logging.info("Ban sistemi aktif!")
except Exception as e:
    logging.error(f"Ban sistemi,hata: {e}")

# -------------------- Ban kaydet --------------------
def save_banned_ips():
    try:
        with open(BANNED_FILE, "w", encoding="utf-8") as f:
            for ip in banned_ips:
                f.write(ip + "\n")
        logging.info("Ban listesi güncellendi.")
    except Exception as e:
        logging.error(f"Ban kaydetme,hata: {e}")

# -------------------- Remote fetch + diff kontrol --------------------
def fetch_remote_text(url, token=None, timeout=5):
    try:
        import requests
        headers = {}
        if token:
            headers['Authorization'] = f'token {token}'
        r = requests.get(url, headers=headers, timeout=timeout)
        r.raise_for_status()
        return r.text
    except Exception:
        try:
            from urllib.request import Request, urlopen
            req = Request(url)
            if token:
                req.add_header('Authorization', f'token {token}')
            with urlopen(req, timeout=timeout) as resp:
                return resp.read().decode('utf-8', errors='replace')
        except Exception as e:
            logging.warning(f"Uzak dosya alınamadı: {e}")
            return None

def local_remote_differs(local_path, remote_raw_url, start_line=1, token=None):
    try:
        local_mtime = os.path.getmtime(local_path)
    except Exception:
        local_mtime = None

    now = time.time()
    if (VERSION_CACHE["url"] == remote_raw_url and
        VERSION_CACHE["start_line"] == start_line and
        VERSION_CACHE["local_mtime"] == local_mtime and
        (now - VERSION_CACHE["time"]) < VERSION_CACHE_TTL):
        return VERSION_CACHE["result"]

    remote_text = fetch_remote_text(remote_raw_url, token=token)
    if remote_text is None:
        VERSION_CACHE.update({
            "time": now,
            "result": None,
            "local_mtime": local_mtime,
            "url": remote_raw_url,
            "start_line": start_line
        })
        return None

    try:
        with open(local_path, "r", encoding="utf-8", errors="replace") as f:
            local_text = f.read()
    except Exception as e:
        logging.warning(f"Yerel dosya okunamadı: {e}")
        VERSION_CACHE.update({
            "time": now,
            "result": None,
            "local_mtime": local_mtime,
            "url": remote_raw_url,
            "start_line": start_line
        })
        return None

    remote_lines = remote_text.splitlines()
    local_lines = local_text.splitlines()
    i = max(0, start_line - 1)
    differs = False
    for a, b in zip(remote_lines[i:], local_lines[i:]):
        if a.rstrip() != b.rstrip():
            differs = True
            break
    if not differs and len(remote_lines[i:]) != len(local_lines[i:]):
        differs = True

    VERSION_CACHE.update({
        "time": now,
        "result": differs,
        "local_mtime": local_mtime,
        "url": remote_raw_url,
        "start_line": start_line
    })
    return differs

# -------------------- Broadcast --------------------
def broadcast(message, sender=None):
    with lock:
        snapshot = clients[:]
    for c in snapshot:
        if c == sender:
            continue
        try:
            c.send(message.encode('utf-8'))
        except Exception as e:
            try:
                with lock:
                    if c in clients:
                        idx = clients.index(c)
                        clients.pop(idx)
                        try:
                            nicknames.pop(idx)
                        except:
                            pass
                        try:
                            client_ips.pop(idx)
                        except:
                            pass
                last_activity.pop(c, None)
                last_ping.pop(c, None)
                c.close()
            except Exception:
                pass
            logging.warning(f"Broadcast gönderim hatası: {e}")

# -------------------- Client handler --------------------
def handle(client, nickname, ip):
    last_activity[client] = time.time()
    last_ping[client] = None

    while True:
        try:
            raw = client.recv(RECV_BUFFER)
            if not raw:
                break

            msg = raw.decode('utf-8', errors='replace').strip()
            last_activity[client] = time.time()
            last_ping[client] = None

            if not msg:
                continue

            if msg.upper() == "PONG":
                continue

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

                elif cmd == "/pm" and len(parts) == 3:
                    target_name = parts[1]
                    private_msg = parts[2]
                    with lock:
                        if target_name in nicknames:
                            target_index = nicknames.index(target_name)
                            target_client = clients[target_index]
                            try:
                                target_client.send(f"[Özel] {nickname}: {private_msg}".encode('utf-8'))
                                client.send(f"[Özel] {nickname} -> {target_name}: {private_msg}".encode('utf-8'))
                            except Exception as e:
                                logging.warning(f"PM gönderme hatası: {e}")
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
                full_message = f"[{nickname}]: {msg}"
                logging.info(full_message)
                broadcast(full_message, client)

        except Exception as e:
            logging.warning(f"Client handler,hata: {e}")
            break

    with lock:
        if client in clients:
            try:
                idx = clients.index(client)
                clients.pop(idx)
                try:
                    nicknames.pop(idx)
                except:
                    pass
                try:
                    client_ips.pop(idx)
                except:
                    pass
            except ValueError:
                pass
    try:
        client.close()
    except:
        pass
    last_activity.pop(client, None)
    last_ping.pop(client, None)
    broadcast(f"{nickname} ayrıldı!\n")
    logging.info(f"{nickname} ayrıldı.")

# -------------------- Ping & idle monitor --------------------
def ping_idle_monitor():
    while True:
        time.sleep(PING_INTERVAL)
        now = time.time()
        with lock:
            snapshot = clients[:]
        for c in snapshot:
            try:
                la = last_activity.get(c, None)
                lp = last_ping.get(c, None)
                if la is None:
                    try:
                        with lock:
                            if c in clients:
                                idx = clients.index(c)
                                clients.pop(idx)
                                try:
                                    nicknames.pop(idx)
                                except:
                                    pass
                                try:
                                    client_ips.pop(idx)
                                except:
                                    pass
                    except:
                        pass
                    try:
                        c.close()
                    except:
                        pass
                    last_activity.pop(c, None)
                    last_ping.pop(c, None)
                    continue

                if now - la > IDLE_LIMIT:
                    logging.info("Idle limit aşıldı, client kapatılıyor.")
                    try:
                        c.send("Zaman aşımı (idle). Bağlantı kapatılıyor.\n".encode('utf-8'))
                    except:
                        pass
                    try:
                        with lock:
                            if c in clients:
                                idx = clients.index(c)
                                clients.pop(idx)
                                nicknames.pop(idx)
                                client_ips.pop(idx)
                    except:
                        pass
                    try:
                        c.close()
                    except:
                        pass
                    last_activity.pop(c, None)
                    last_ping.pop(c, None)
                    continue

                if now - la > PING_THRESHOLD:
                    if lp is None:
                        try:
                            c.send("PING\n".encode('utf-8'))
                            last_ping[c] = now
                        except Exception as e:
                            logging.warning(f"PING gönderilemedi: {e}")
                            try:
                                with lock:
                                    if c in clients:
                                        idx = clients.index(c)
                                        clients.pop(idx)
                                        nicknames.pop(idx)
                                        client_ips.pop(idx)
                            except:
                                pass
                            try:
                                c.close()
                            except:
                                pass
                            last_activity.pop(c, None)
                            last_ping.pop(c, None)
                    else:
                        if now - lp > PONG_TIMEOUT:
                            logging.info("PONG gelmedi, client kapatılıyor.")
                            try:
                                with lock:
                                    if c in clients:
                                        idx = clients.index(c)
                                        clients.pop(idx)
                                        nicknames.pop(idx)
                                        client_ips.pop(idx)
                            except:
                                pass
                            try:
                                c.close()
                            except:
                                pass
                            last_activity.pop(c, None)
                            last_ping.pop(c, None)
            except Exception as e:
                logging.warning(f"Ping monitor hata: {e}")
                try:
                    with lock:
                        if c in clients:
                            idx = clients.index(c)
                            clients.pop(idx)
                            try:
                                nicknames.pop(idx)
                            except:
                                pass
                            try:
                                client_ips.pop(idx)
                            except:
                                pass
                except:
                    pass
                try:
                    c.close()
                except:
                    pass
                last_activity.pop(c, None)
                last_ping.pop(c, None)

# -------------------- Receive loop --------------------
def receive_loop():
    while True:
        try:
            client, address = server.accept()
            ip = address[0]

            if ip in banned_ips:
                try:
                    client.send("Bu IP yasaklı!\n".encode('utf-8'))
                except:
                    pass
                client.close()
                continue

            # IP başına limit kontrolü
            with lock:
                ip_count = client_ips.count(ip)
                if ip_count >= MAX_PER_IP:
                    try:
                        client.send("Bu IP için izin verilen maksimum bağlantı sayısı aşıldı.\n".encode('utf-8'))
                    except:
                        pass
                    client.close()
                    continue

            try:
                password = client.recv(RECV_BUFFER).decode('utf-8', errors='replace').strip()
            except Exception:
                client.close()
                continue
            if password != SERVER_PASSWORD:
                try:
                    client.send("Hatalı şifre!\n".encode('utf-8'))
                except:
                    pass
                client.close()
                continue

            try:
                client.send("Lütfen adınızı girin: ".encode('utf-8'))
                nickname = client.recv(RECV_BUFFER).decode('utf-8', errors='replace').strip() or "Anonim"
            except Exception:
                client.close()
                continue

            if not NICK_REGEX.match(nickname) or nickname.strip() == "":
                try:
                    client.send("Takma ad yalnızca 1-20 karakter arası, harf/rakam/altçizgi/tire/boşluk içerebilir.\n".encode('utf-8'))
                except:
                    pass
                client.close()
                continue

            # ------------------- GITHUB KARŞILAŞTIRMA -------------------
            try:
                diff = local_remote_differs(LOCAL_SERVER_PATH, GITHUB_RAW_URL, start_line=CHECK_FROM_LINE, token=GITHUB_TOKEN)
                if diff is None:
                    try:
                        client.send("Uyarı: Versiyon kontrolü yapılamadı (remote dosya ulaşılamadı veya yerel okunamadı).\n".encode('utf-8'))
                    except:
                        pass
                elif diff:
                    warning = "UYARI: Bu sunucunun versiyonu GitHub'taki referans dosyayla farklı veya modifiyelidir.\n"
                    try:
                        client.send(warning.encode('utf-8'))
                    except Exception as e:
                        logging.warning(f"Versiyon uyarısı gönderilemedi: {e}")
            except Exception as e:
                logging.warning(f"Versiyon kontrolü sırasında hata: {e}")
            # ------------------- GITHUB KARŞILAŞTIRMA -------------------

            with lock:
                if nickname in nicknames:
                    try:
                        client.send("Bu takma ad zaten kullanılıyor.\n".encode('utf-8'))
                    except:
                        pass
                    client.close()
                    continue

                clients.append(client)
                nicknames.append(nickname)
                client_ips.append(ip)

            last_activity[client] = time.time()
            last_ping[client] = None

            logging.info(f"{ip} bağlandı. Takma ad: {nickname}")
            broadcast(f"{nickname} sohbete katıldı!\n", client)
            threading.Thread(target=handle, args=(client, nickname, ip), daemon=True).start()

        except socket.timeout:
            continue
        except OSError:
            logging.info("Sunucu kapatıldı, accept döngüsü durduruluyor.")
            break
        except Exception as e:
            logging.warning(f"Giriş denetimi,hata: {e}")

# -------------------- Server commands --------------------
def server_commands():
    while True:
        cmd = input()
        parts = cmd.split(" ", 2)
        command = parts[0].lower()

        if command == "/help":
            help_text = (
                "/shutdown -> Sunucuyu kapatır\n"
                "/kick <kullanıcı>\n"
                "/ban <kullanıcı>\n"
                "/unban <IP>\n"
                "/say <mesaj>\n"
                "/list\n"
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
                clients.clear()
                nicknames.clear()
                client_ips.clear()
            try:
                server.close()
            except:
                pass
            logging.info("Sunucu kapatıldı.")
            os._exit(0)

        elif command == "/kick" and len(parts) >= 2:
            kick_name = parts[1]
            with lock:
                if kick_name in nicknames:
                    idx = nicknames.index(kick_name)
                    kicked_client = clients[idx]
                    try:
                        kicked_client.send("Sunucudan atıldınız.\n".encode('utf-8'))
                    except:
                        pass
                    try:
                        kicked_client.close()
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
                    last_activity.pop(kicked_client, None)
                    last_ping.pop(kicked_client, None)
                    broadcast(f"{kick_name} sunucudan atıldı!\n")
                    logging.info(f"{kick_name} atıldı.")
                else:
                    logging.info(f"Kullanıcı {kick_name} bulunamadı.")

        elif command == "/ban" and len(parts) >= 2:
            ban_name = parts[1]
            with lock:
                if ban_name in nicknames:
                    idx = nicknames.index(ban_name)
                    ip = client_ips[idx]
                    banned_ips.add(ip)
                    save_banned_ips()
                    try:
                        clients[idx].send("Banlandınız!\n".encode('utf-8'))
                    except:
                        pass
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
                    last_activity.pop(clients[idx] if idx < len(clients) else None, None)
                    last_ping.pop(clients[idx] if idx < len(clients) else None, None)
                    broadcast(f"{ban_name} yasaklandı!\n")
                    logging.info(f"{ban_name} banlandı (IP: {ip}).")
                else:
                    logging.info(f"Kullanıcı {ban_name} bulunamadı.")

        elif command == "/unban" and len(parts) >= 2:
            ip = parts[1]
            if ip in banned_ips:
                banned_ips.remove(ip)
                save_banned_ips()
                logging.info(f"{ip} ban kaldırıldı.")
                broadcast(f"{ip} banı kaldırıldı!\n")
            else:
                logging.info(f"{ip} banlı değil.")

        elif command == "/say" and len(parts) >= 2:
            message = " ".join(parts[1:])
            broadcast(f"[Sunucu]: {message}\n")
            logging.info(f"[Sunucu]: {message}")

        elif command == "/list":
            with lock:
                logging.info(f"Bağlı kullanıcılar: {', '.join(nicknames)}")

# -------------------- Start server --------------------
try:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    server.listen(LISTEN_BACKLOG)
    server.settimeout(5)
    logging.info(f"Sunucu başlatıldı: {HOST}:{PORT} (backlog={LISTEN_BACKLOG})")
except Exception as e:
    logging.error(f"Sunucu soketi,hata: {e}")

try:
    threading.Thread(target=ping_idle_monitor, daemon=True).start()
    logging.info("Ping/Idle monitörü aktif.")
except Exception as e:
    logging.error(f"Ping monitörü başlatılamadı: {e}")

try:
    threading.Thread(target=server_commands, daemon=True).start()
    logging.info("Komut sistemi aktif!")
except Exception as e:
    logging.error(f"Komut sistemi,hata: {e}")

try:
    logging.info("Bağlantı dinleme başlatılıyor...")
    receive_loop()
except Exception as e:
    logging.error(f"Bağlantı dinleme hatası: {e}")
