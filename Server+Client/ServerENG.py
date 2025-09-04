import socket
import threading
import os
import time
from queue import Queue, Full, Empty

broadcast_queue = Queue(maxsize=2000)
muted_users = {}
running = True  

VERSION = "S.T.C.S. v0.1.1-Alpha(Test) , Github: https://github.com/Darkfoxy5/S.T.C.S. "
HOST = '0.0.0.0'
PORT = 5555

SERVER_PASSWORD = "12345"  # Put the password here, "12345" is the default public server password.
RULES = "Write the rules here"

clients = []
nicknames = []
client_ips = []
banned_ips = set()
lock = threading.Lock()
BANNED_FILE = "banned_ips.txt"

# Spam control
message_counts = {}

# Load banned IPs
try:
    if os.path.exists(BANNED_FILE):
        with open(BANNED_FILE, "r") as f:
            for line in f:
                banned_ips.add(line.strip())
    print("Ban system active!")
except Exception as e:
    print(f"Ban system failed to start: {e}")

# Ban IP saving
try:
    def save_banned_ips():
        with open(BANNED_FILE, "w") as f:
            for ip in banned_ips:
                f.write(ip + "\n")
    print("Ban saving system active!")
except Exception as e:
    print(f"Ban saving system failed to start: {e}")

# Broadcast system
try:
    def broadcast_worker():
        while running:
            try:
                message, sender = broadcast_queue.get(timeout=1)
            except Empty:
                continue
            disconnected_clients = []
            with lock:
                for c in clients[:]:
                    if c != sender:
                        try:
                            c.send(message.encode('utf-8'))
                        except (socket.error, ConnectionResetError, OSError):
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
                        print(f"{removed_nick} removed from list during broadcast.")
            broadcast_queue.task_done()

    def broadcast(message, sender=None):
        try:
            broadcast_queue.put_nowait((message, sender))
        except Full:
            pass

    threading.Thread(target=broadcast_worker, daemon=True).start()
    print("Broadcast system active!")
except Exception as e:
    print(f"Broadcast system failed to start: {e}")

# Client removal
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

    broadcast(f"{nickname} left!\n", None)
    print(f"{nickname} left.")

def handle(client, nickname, ip):
    # messages per time window
    time_window = 10
    message_limit = 12

    while running:
        try:
            raw = client.recv(1024)
            if not raw:
                break

            with lock:
                expiry = muted_users.get(nickname)
            if expiry:
                if time.time() < expiry:
                    try:
                        client.send("You are muted, cannot send messages.\n".encode('utf-8'))
                    except:
                        pass
                    continue
                else:
                    with lock:
                        muted_users.pop(nickname, None)

            if len(raw) > 1024:
                try:
                    client.send("Message too long!\n".encode('utf-8'))
                except:
                    pass
                continue

            msg = raw.decode('utf-8', errors='replace').strip()
            if not msg:
                break

            current_time = time.time()
            with lock:
                last_time, count = message_counts.get(nickname, (current_time, 0))
                if current_time - last_time <= time_window:
                    count += 1
                else:
                    count = 1
                    last_time = current_time
                message_counts[nickname] = (last_time, count)
                over_limit = (count > message_limit)

            if over_limit:
                try:
                    client.send("Flood detected, connection closing!\n".encode('utf-8'))
                except:
                    pass
                remove_client(client, nickname)
                break

            # Commands
            if msg.startswith("/"):
                parts = msg.split(" ", 2)
                cmd = parts[0].lower()

                if cmd == "/list":
                    with lock:
                        user_list = ", ".join(nicknames)
                    try:
                        client.send(f"Connected users: {user_list}\n".encode('utf-8'))
                    except:
                        pass

                elif cmd == "/v":
                    try:
                        client.send(f"Server version: {VERSION}\n".encode('utf-8'))
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
                            target_client.send(f"[Private] {nickname}: {private_msg}".encode('utf-8'))
                            client.send(f"[Private] {nickname} -> {target_name}: {private_msg}".encode('utf-8'))
                        except:
                            try:
                                client.send(f"User {target_name} not online.\n".encode('utf-8'))
                            except:
                                pass
                    else:
                        try:
                            client.send(f"User {target_name} not found.\n".encode('utf-8'))
                        except:
                            pass

                else:
                    try:
                        client.send("Unknown or unauthorized command.\n".encode('utf-8'))
                    except:
                        pass
            else:
                # message
                full_message = f"{nickname}: {msg}"
                print(full_message)
                broadcast(full_message, client)

        except (ConnectionResetError, OSError) as e:
            print(f"{nickname} connection abruptly closed: {e}.")
            remove_client(client, nickname)
            break

        except socket.timeout:
            try:
                client.send("Connection closed due to 5 minutes of inactivity.\n".encode('utf-8'))
            except:
                pass
            remove_client(client, nickname)
            print(f"{nickname} disconnected due to timeout.")
            break

        except Exception as e:
            print(f"{nickname} connection unexpectedly closed: {e}")
            remove_client(client, nickname)
            break

# DDoS prevention
MAX_CONNECTIONS_PER_IP = 3
MIN_CONNECTION_INTERVAL = 2  # seconds
last_connection_time = {}

def receive():
    server.listen(100)
    print(f"Server running on {HOST}:{PORT}...")
    while running:
        try:
            client, address = server.accept()
            client.settimeout(300)  # timeout 5 minutes
        except socket.timeout:
            continue
        except (socket.error, OSError, ConnectionResetError) as e:
            print(f"Connection error on accept: {e}")
            continue

        ip = address[0]
        now = time.time()

        # Minimum connection interval
        if ip in last_connection_time and now - last_connection_time[ip] < MIN_CONNECTION_INTERVAL:
            try:
                client.send("Connecting too fast! Please wait.\n".encode('utf-8'))
            except:
                pass
            client.close()
            continue
        last_connection_time[ip] = now

        # Max simultaneous connections per IP
        if client_ips.count(ip) >= MAX_CONNECTIONS_PER_IP:
            try:
                client.send(f"This IP already has {MAX_CONNECTIONS_PER_IP} sessions! Please wait.\n".encode('utf-8'))
            except:
                pass
            client.close()
            continue

        # Ban check
        if ip in banned_ips:
            try:
                client.send("This IP is banned!\n".encode('utf-8'))
            except:
                pass
            try:
                client.close()
            except:
                pass
            continue

        if ip in client_ips:
            try:
                client.send("This IP is already connected! Cannot open multiple sessions.\n".encode('utf-8'))
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

        # Password check
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
                client.send("Wrong password!\n".encode('utf-8'))
            except:
                pass
            try:
                client.close()
            except:
                pass
            continue

        # Ask for nickname
        try:
            client.send("Please enter your name: ".encode('utf-8'))
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
            nickname = "Anonymous"

        if nickname in nicknames:
            try:
                client.send("This nickname is already taken.\n".encode('utf-8'))
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

        print(f"{ip} connected. Nickname: {nickname}")
        broadcast(f"{nickname} joined the chat!\n", client)
        try:
            client.send("Welcome to the chat!\n".encode('utf-8'))
            client.send(f"Server version: {VERSION}\n".encode('utf-8'))
            client.send(f"Rules: {RULES}\n".encode('utf-8'))
        except:
            remove_client(client, nickname)
            continue

        thread = threading.Thread(target=handle, args=(client, nickname, ip), daemon=True)
        thread.start()
#Administrator commands
def server_commands():
    while True:
        cmd = input()
        parts = cmd.split(" ", 2)
        command = parts[0].lower()

        if command == "/help":
            help_text = (
                "Commands available for the server terminal:(31.08.2025)\n"
                "/shutdown -> Shuts down the server\n"
                "/v -> Displays the version of the server you are on\n"
                "/kick <kullanıcı> -> kick the selected user\n"
                "/ban <kullanıcı> -> Banned the selected user\n"
                "/unban <IP> -> Un-Banned the selected user\n"
                "/say <mesaj> -> Sends a message to the chat window as a server\n"
                "/list -> Lists connected users\n"
            )
            print(help_text)
            continue

        if command == "/shutdown":
            broadcast("The server is shutting down...\n")
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
            print("The server has been shut down.")
            import os; os._exit(0)

        elif command == "/kick" and len(parts) >= 2:
            kick_name = parts[1]
            if kick_name in nicknames:
                idx = nicknames.index(kick_name)
                kicked_client = clients[idx]
                ip = client_ips[idx]
                kicked_client.send("You've been kicked from the server.\n".encode('utf-8'))
                kicked_client.close()
                broadcast(f"{kick_name} was kicked from the server!\n")
                print(f"{kick_name} was kick.")
            else:
                print(f"User {kick_name} not be found.")

        elif command == "/ban" and len(parts) >= 2:
            ban_name = parts[1]
            if ban_name in nicknames:
                idx = nicknames.index(ban_name)
                ip = client_ips[idx]
                with lock:
                    banned_ips.add(ip)
                    save_banned_ips()
                clients[idx].send("You have been banned!\n".encode('utf-8'))
                clients[idx].close()
                broadcast(f"{ban_name} was banned!\n")
                print(f"{ban_name} banned (IP: {ip}).")
            else:
                print(f"User {ban_name} not be found.")

        elif command == "/unban" and len(parts) >= 2:
            ip = parts[1]
            if ip in banned_ips:
                with lock:
                    banned_ips.remove(ip)
                    save_banned_ips()
                print(f"{ip} The ban has been lifted.")
                broadcast(f"{ip} ban has been lifted!\n")
            else:
                print(f"{ip} not banned.")

        elif command == "/say" and len(parts) >= 2:
            message = " ".join(parts[1:])
            broadcast(f"[Server]: {message}\n")
            print(f"[Server]: {message}")

        elif command == "/list":
            with lock:
                user_list = ", ".join(nicknames)
            print(f"Connected users: {', '.join(nicknames)}")

        elif cmd == "/v":
            print(f"Server Version: {VERSION}")      

try:
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
    server.bind((HOST, PORT))
    print("Server socket active!")
except Exception as e:
    print(f"The server socket failed to start: {e}")

try:
    threading.Thread(target=server_commands, daemon=True).start()
    print("The server command system is active!")
except Exception as e:
    print(f"The command system failed to start: {e}")

try:
    print("Connection listening is starting...")
    receive()
except Exception as e:

    print(f"Connection listening could not be started: {e}")
