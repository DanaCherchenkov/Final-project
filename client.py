import socket
import threading
import time
import os

from consts import ClientToServerMsg, ServerToClientMsgType, ClientToServerMsgType, \
    UDP_MAX_DATAGRAM_SIZE, calculate_checksum, SERVER_IP
from consts import SERVER_NICKNAME, SERVER_TCP_BIND_PORT

SERVER_FILE_LIST = []
CHOSEN_FILE_NUMBER = 0
CLIENT_FILES_DIR = os.path.join(os.path.dirname(__file__), 'client_files')


# the input from the user
def handle_int_input(menu_text):
    while True:
        try:
            result = int(input())
        except ValueError:
            print("[-] Error: Invalid input, please insert a number in the correct range")
        else:
            break
    return result


# print all the files in the server
def print_server_files(msg_type, message_data):
    all_files = message_data.split("#")
    if msg_type == ServerToClientMsgType.REPLAY_ALL_FILES.value:
        print(f"[+] All files in server: ")
    elif msg_type == ClientToServerMsgType.DOWNLOAD_FILE.value:
        print(f"[+] Please choose file number to download: ")
    files_counter = 1
    for filename in all_files:
        print(f"   [{str(files_counter)}] {filename}")
        files_counter = files_counter + 1
    return all_files


def send_message(sock, message: ClientToServerMsg):
    """
    Client -> Server
    |<ClientToServerMsgType>~<MessageData>|
    """
    sock.send(f"|{str(message.msg_type.value)}~{str(message.message_data)}|".encode())


def recv_message(sock):
    """
    Server -> Client
    |<ServerToClientMsgType>~<SenderNickName>~<MessageData>|
    """
    msg = sock.recv(1024)
    if msg.decode() == "":
        print(f"[-] You was disconnected from the server, the client will now terminate")
        os._exit(0)
    new_message: str = msg.decode().split("|")[1]
    msg_list = new_message.split("~")
    server_to_client_msg_type, sender_nickname, message_data = msg_list
    return int(server_to_client_msg_type), sender_nickname, message_data


def recv_thread(client):
    while True:
        try:
            msg_type, sender_nickname, message_data = recv_message(client)

            if msg_type == ServerToClientMsgType.CONNECTED.value:
                print("[+] Incoming from server: " + message_data)
            elif msg_type == ServerToClientMsgType.DISCONNECTED.value:
                print(f"[-] You was disconnected from the server, the client will now terminate")
                os._exit(0)
            elif msg_type == ServerToClientMsgType.MESSAGE_USER.value:
                print(f"[+] Incoming message from {sender_nickname}: {message_data}")
            elif msg_type == ServerToClientMsgType.REPLAY_ALL_CLIENTS.value:
                all_clients = message_data.split("%")
                print(f"[+] All connected clients: ")
                client_count = 1
                for client_nickname in all_clients:
                    print(f"   [{str(client_count)}] {client_nickname}")
                    client_count = client_count + 1
            elif msg_type == ServerToClientMsgType.REPLAY_ALL_FILES.value:
                global SERVER_FILE_LIST
                SERVER_FILE_LIST = print_server_files(ServerToClientMsgType.REPLAY_ALL_FILES.value, message_data)
            elif msg_type == ServerToClientMsgType.REPLAY_ALL_MESSAGES.value:
                if "<>" in message_data:
                    msgs_list = message_data.split("<>")
                    print("[+] All your messages from the server")
                    msg_count = 1
                    for msg in msgs_list:
                        print(f"   [{msg_count}] {msg}")
                        msg_count += 1
                else:
                    print(f"[-] {message_data}")
            elif msg_type == ServerToClientMsgType.DOWNLOAD_FILE.value:
                udp_server_port, file_size = message_data.split("<>")
                udp_server_port = int(udp_server_port)
                file_size = int(file_size)
                udp_recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
                udp_send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)

                udp_recv_sock.bind(("", 0))
                udp_client_port = udp_recv_sock.getsockname()[1]
                udp_send_sock.sendto(str(udp_client_port).encode(), (SERVER_IP, udp_server_port))

                file_name = SERVER_FILE_LIST[int(CHOSEN_FILE_NUMBER) - 1]
                with open(os.path.join(CLIENT_FILES_DIR, file_name), "wb") as f:
                    expecting_seq = 0
                    offset = 0
                    while offset < file_size:
                        """
                        UDP Packet Structure:

                        Server -> Client (data packets)
                            <sequence number: 1><checksum: 4><data: the rest>

                        Client -> Server (acknowledge packets)
                            <sequence number: 1><checksum: 4>
                        """
                        msg, server_addr = udp_recv_sock.recvfrom(UDP_MAX_DATAGRAM_SIZE)
                        # if msg.decode() == "pause":
                        #     try:
                        #         choices = ["yes", "no"]
                        #         usr_input = input("Do you want to continue download? (type in 'yes' or 'no' only)")
                        #         while usr_input not in choices:
                        #             usr_input = input("Do you want to continue download? ('yes' or 'no' only...)")
                        #         udp_send_sock.sendto(str(usr_input).encode(), (SERVER_IP, udp_server_port))
                        #     except Exception:
                        #         pass
                        seq = int(chr(msg[0]))
                        checksum = msg[1:5]
                        data = msg[5:]

                        if seq != expecting_seq:
                            # Unexpected sequence number
                            continue
                        if calculate_checksum(data) != checksum.decode():
                            # Invalid checksum - skip packet
                            continue
                        ack_response = str(seq) + checksum.decode()
                        udp_send_sock.sendto(ack_response.encode(), (SERVER_IP, udp_server_port))
                        f.write(data)
                        expecting_seq += 1
                        offset += len(data)

        except Exception as e:
            print(e)
            print("[-] The client will now terminate\n")
            os._exit(0)


def client_main():
    nick = input("[+] Enter your nickname >>> ")
    while nick == SERVER_NICKNAME:
        nick = input("[-] Invalid nickname, you cannot use the server's name\n[+] Enter your nickname again >>> ")

    client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    client.connect(('127.0.0.1', SERVER_TCP_BIND_PORT))
    client.send(nick.encode())

    thread = threading.Thread(target=recv_thread, args=(client,))
    thread.start()
    while True:
        time.sleep(0.5)
        print("\n[+] Server message types: ")
        for data in ClientToServerMsgType:
            if data.name != ClientToServerMsgType.MAX_VALUE.name:
                print('  {:15} = {}'.format(data.name, data.value))  # print the enum of the menu
        msg_type = handle_int_input("[!] Enter message type number >>>\n")
        while msg_type not in range(1, ClientToServerMsgType.MAX_VALUE.value):
            try:
                int(input("[-] Error: Message type not available in the server, please try again"))
                msg_type = handle_int_input("[!] Enter message type number >>>\n")
            except ValueError:
                print("[-] Error: Invalid input, please insert a number in the server's range")
                continue

        if msg_type == ClientToServerMsgType.CONNECT.value:
            msg_data = "Connect"
        elif msg_type == ClientToServerMsgType.DISCONNECT.value:
            msg_data = "Disconnect"
        elif msg_type == ClientToServerMsgType.MESSAGE_USER.value:
            recipient_nickname = input('[-] Please insert exact recipient nickname >>> ')
            msg_content = input('[-] Please insert message content >>> ')
            msg_data = recipient_nickname + ';;' + msg_content
        elif msg_type == ClientToServerMsgType.MESSAGE_ALL.value:
            msg_data = input('[-] Please insert message content >>> ')
        elif msg_type == ClientToServerMsgType.GET_ALL_CLIENTS.value:
            msg_data = ""
        elif msg_type == ClientToServerMsgType.GET_ALL_FILES.value:
            msg_data = ""
        elif msg_type == ClientToServerMsgType.DOWNLOAD_FILE.value:
            msg = ClientToServerMsg(msg_type=ClientToServerMsgType(ClientToServerMsgType.GET_ALL_FILES.value),
                                    message_data="")
            client.send(msg.to_string().encode())
            global CHOSEN_FILE_NUMBER
            CHOSEN_FILE_NUMBER = handle_int_input("[!] Please enter file number to download >>> ")
            msg_data = SERVER_FILE_LIST[int(CHOSEN_FILE_NUMBER) - 1]
        else:
            msg_data = ""
        msg = ClientToServerMsg(msg_type=ClientToServerMsgType(msg_type),
                                message_data=msg_data)
        client.send(msg.to_string().encode())
        print(f"[+] Message type {msg_type} sent!")


if __name__ == '__main__':
    client_main()
