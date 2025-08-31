import socket
import threading
import os

VERSION = "S.T.C.S. v0.1.0-Alpha , Github: https://github.com/Darkfoxy5/S.T.C.S. "
HOST = '0.0.0.0'
PORT = 5555

# The server password is requested when logging into the server.
SERVER_PASSWORD = "Enter the password here"
#Server Rules are displayed when a user logs in for the first time.
RULES = "Write the Server Rules here"

clients = []
nicknames = []
client_ips = []
banned_ips = set()
lock = threading.Lock()
BANNED_FILE = "banned_ips.txt"

# Load Banned IP's
try:
    if os.path.exists(BANNED_FILE):
        with open(BANNED_FILE, "r") as f:
            for line in f:
                banned_ips.add(line.strip())
    print("The ban system is active!")
except Exception as e:
    print(f"The ban system failed to start: {e}")

#Ban IP logs
try:
    def save_banned_ips():
        with open(BANNED_FILE, "w") as f:
            for ip in banned_ips:
                f.write(ip + "\n")
    print("Ban logging system active!")
except Exception as e:
    print(f"Ban logging system failed to start: {e}")

# The broadcast system
try:
    def broadcast(message, sender=None):
        with lock:
            for c in clients[:]:
                if c != sender:
                    try:
                        c.send(message.encode('utf-8'))
                    except (ConnectionResetError, OSError) as e:
                            idx = clients.index(c)
                            removed_nick = nicknames[idx]
                            clients.pop(idx)
                            nicknames.pop(idx)
                            client_ips.pop(idx)
                            print(f"{removed_nick} connection lost during broadcast: {e}")

    print("The broadcast system is active!")
except Exception as e:
    print(f"The broadcast system failed to start: {e}")

try:
   def handle(client, nickname, ip):
    while True:
        try:
            msg = client.recv(1024).decode('utf-8').strip()
            if not msg:
                break

            if msg.startswith("/"):
                parts = msg.split(" ", 2)
                cmd = parts[0].lower()

                if cmd == "/list":
                    with lock:
                        user_list = ", ".join(nicknames)
                    client.send(f"Connected users: {user_list}\n".encode('utf-8'))

                elif cmd == "/v":
                    client.send(f"Server version: {VERSION}\n".encode('utf-8'))

                elif cmd == "/pm" and len(parts) == 3:
                    target_name = parts[1]
                    private_msg = parts[2]

                    with lock:
                        if target_name in nicknames:
                            target_index = nicknames.index(target_name)
                            target_client = clients[target_index]
                        else:
                            target_client = None

                    if target_client:
                        try:
                            target_client.send(f"[Private] {nickname}: {private_msg}".encode('utf-8'))
                            client.send(f"[Private] {nickname} -> {target_name}: {private_msg}".encode('utf-8'))
                        except (ConnectionResetError, OSError):
                            client.send(f"User {target_name} is currently not online.\n".encode('utf-8'))
                    else:
                        client.send(f"User {target_name} not found.\n".encode('utf-8'))

                else:
                    client.send("Unknown command or unauthorized user.\n".encode('utf-8'))

            else:
                full_message = f"{nickname}: {msg}"
                print(full_message)
                broadcast(full_message, client)

        except Exception as e:
            print(f"{nickname} , connection unexpectedly disconnected: {e}")
            break

    with lock:
        if client in clients:
            index = clients.index(client)
            clients.pop(index)
            nicknames.pop(index)
            client_ips.pop(index)

    try:
        client.close()
    except:
        pass
    broadcast(f"{nickname} left!\n", None)
    print(f"{nickname} left.")
    print("Handle system active!")
except Exception as e:
    print(f"The handle system failed to start: {e}")

#Entry inspection
try:
    def receive():
        server.listen()
        print(f"The server is running at {HOST}:{PORT}...")
        while True:
            try:
                client, address = server.accept()
            except (OSError, ConnectionResetError) as e:
                print(f"Connection error during server acceptance: {e}")
                break

            ip = address[0]

            if ip in banned_ips:
                client.send("This IP is banned!\n".encode('utf-8'))
                client.close()
                continue

            if ip in client_ips:
                client.send("This IP is already connected! You cannot open multiple account.\n".encode('utf-8'))
                client.close()
                continue

            # Password check
            password = client.recv(1024).decode('utf-8').strip()
            if password != SERVER_PASSWORD:
                client.send("Incorrect password!\n".encode('utf-8'))
                client.close()
                continue

            # Request a nickname
            client.send("Please enter your nickname: ".encode('utf-8'))
            nickname = client.recv(1024).decode('utf-8').strip()
            nickname = "_".join(nickname.split())
            if not nickname:
                nickname = "Anonim"

            if nickname in nicknames:
                client.send("This nickname is already in use.\n".encode('utf-8'))
                client.close()
                continue

            with lock:
                clients.append(client)
                nicknames.append(nickname)
                client_ips.append(ip)

            print(f"{ip} connected. Nickname: {nickname}")
            broadcast(f"{nickname} joined the chat!\n", client)
            client.send("Welcome to the chat!\n".encode('utf-8'))
            client.send(f"Server version: {VERSION}\n".encode('utf-8'))
            client.send(f"Kurallar/Rules: {RULES}\n".encode('utf-8'))

            thread = threading.Thread(target=handle, args=(client, nickname, ip), daemon=True)
            thread.start()
    print("Access Control System has started.")   
except Exception as e:
    print(f"Access Control System failed to start: {e}")           

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