import random
import threading
import socket
import os

from consts import ServerToClientMsgType, ClientToServerMsgType, SERVER_NICKNAME, BIND_IP, SERVER_TCP_BIND_PORT, \
    MAX_CONNECTIONS, ServerToClientMsg, PORTS_RANGE, MAX_DATA_SIZE, calculate_checksum, MAX_FILE_SIZE

thread_list = []
CLIENTS_DICT = {}  # key = nickname, value = socket
USER_MSGS_DB = {}  # key = nickname, value = list of msgs


def add_msg_to_db(sender, recipient_nickname, msg_content):
    if recipient_nickname in USER_MSGS_DB.keys():
        USER_MSGS_DB[recipient_nickname] = USER_MSGS_DB[recipient_nickname] + [f"{sender}: {msg_content}"]
    else:
        USER_MSGS_DB[recipient_nickname] = [f"{sender}: {msg_content}"]


def corrupt_packet(packet):
    """
    Corrupt a packet by randomly changing a single byte char
    """
    corruption_index = random.randint(0, len(packet) - 1)
    corrupted_packet = packet[:corruption_index] + str.encode(chr(random.randint(0, 90))) + packet[
                                                                                            corruption_index + 1:]
    return corrupted_packet


def send_file_rdt(message_data, nickname, client_sock):
    file_path = get_file_path_by_name(message_data)
    if os.path.getsize(file_path) > MAX_FILE_SIZE:
        print("[-] Error: Requested file exceeds the protocol limits")
        msg = ServerToClientMsg(sender_nickname=SERVER_NICKNAME,
                                message_type=ServerToClientMsgType.DISCONNECTED,
                                message_data="")
        send_message(target_nickname=nickname, message=msg)
    with open(file_path, "rb") as f:
        data = f.read()
    udp_recv_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    udp_send_sock = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    port = 0

    # Now we are rolling a free port for file transfer
    while True:
        try:
            port = random.randrange(SERVER_TCP_BIND_PORT + 1, SERVER_TCP_BIND_PORT + PORTS_RANGE)
            udp_recv_sock.bind((BIND_IP, port))
        except Exception:
            print("[!] Alert: Chosen port was taken, re-rolling a new port")
            continue
        else:
            # We found free port
            break

    # Notify the client with the chosen port
    msg = ServerToClientMsg(sender_nickname=SERVER_NICKNAME,
                            message_type=ServerToClientMsgType.DOWNLOAD_FILE,
                            message_data=str(port) + "<>" + str(len(data)))
    send_message(target_nickname=nickname, message=msg)

    # Wait for client to connect with udp socket
    client_udp_listening_port, client_udp_address = udp_recv_sock.recvfrom(1024)
    client_ip, _ = client_udp_address

    # From now on we don't want to block, in case client didn't reply with ACK - we will resend the chunk
    udp_recv_sock.settimeout(1)

    total_bytes_client_received = 0
    seq = 0
    while total_bytes_client_received < len(data):
        """
        UDP Packet Structure:

        Server -> Client (data packets)
            <sequence number: 1><checksum: 4><data: the rest>

        Client -> Server (acknowledge packets)
            <sequence number: 1><checksum: 4>

        we only need 1 char for sequence number, maximum seq number is 9 (9 * 64 KB = max file size)
        """
        chunk = data[total_bytes_client_received:total_bytes_client_received + MAX_DATA_SIZE]
        client_ack = False
        while not client_ack:
            packet = str(seq).encode() + str(calculate_checksum(chunk)).encode() + chunk
            udp_send_sock.sendto(packet, (client_ip, int(client_udp_listening_port.decode())))
            try:
                msg = udp_recv_sock.recv(5)  # Sequence number (1 byte) + Checksum (4 bytes)
                ack_seq = int(chr(msg[0]))
                checksum = msg[1:]
                if calculate_checksum(chunk) == checksum.decode() and ack_seq == seq:
                    client_ack = True
            except socket.timeout:
                # let's continue to resend the data again
                print("[-] Timeout: Client didn't manage to send ack for a whole one second")
            except Exception as err:
                print("[-] Error: " + str(err))
                print(err)
        seq += 1
        total_bytes_client_received += len(chunk)
        print(f"[+] User {nickname} downloaded "
              f"{round(total_bytes_client_received / len(data) * 100, 2)}% of the file "
              f"{os.path.basename(file_path)}. Last byte is: {chunk[-1]}")
        # if download_pause:
        #     print(f"[-] Pausing download for user {nickname} until reconfirmation")
        #     udp_send_sock.sendto("pause".encode(), (client_ip, int(client_udp_listening_port.decode())))
        #     reply = udp_recv_sock.recv(1024)
        #     if reply == "no":
        #         terminate_download = False
        #         break
        #     else:
        #         download_pause = False


def get_file_path_by_name(file_name):
    current_dir = os.path.abspath(os.getcwd())  # getcwd = the current path
    server_dir = os.path.join(current_dir, 'server_files')
    all_file_paths = os.listdir(server_dir)
    for file in all_file_paths:
        if file_name in file:
            return os.path.join(server_dir, file)
    else:
        return "File not found!"


def remove_and_disconnect_from_client(client, nickname):
    """
    Closes the client socket and removes it from the servers current connection.
    This method will cal socket.close() which will send an empty close session string to the
    client which will cause it to terminate

    :param client: The current client socket
    :param nickname: The client nickname to remove
    :return: void
    """
    client.close()
    CLIENTS_DICT.pop(nickname)
    print(f"[!] Client: {nickname} was disconnected successfully")


def get_server_folder_content():
    """
    iterates over the content of the server_files directory under the projects main directory
    and returns all it's content file names.

    :return: String of all file names divided by # for later splitting
    file1#file2#file3  (for a folder with only 3 files)
    """
    current_dir = os.path.abspath(os.getcwd())
    server_dir = os.path.join(current_dir, 'server_files')
    all_file_paths = os.listdir(server_dir)
    all_files_lst = []
    for file in all_file_paths:
        all_files_lst.append(os.path.basename(file))
    all_files_str = "#".join(all_files_lst)
    return all_files_str


def send_message(target_nickname: str, message: ServerToClientMsg):
    """
    Server -> Client
    |<ServerToClientMsgType>~<SenderNickName>~<MessageData>|
    """
    client_sock = CLIENTS_DICT[target_nickname]
    client_sock.send(
        f"|{str(message.message_type_num)}~{str(message.sender_nickname)}~{str(message.message_data)}|".encode())


def recv_message(client):
    """
    Client -> Server
    |<ClientToServerMsgType>~<MessageData>|
    """
    msg = client.recv(1024)
    new_message: str = msg.decode().split("|")[1]
    msg_list = new_message.split("~")
    request_type, message_data = msg_list
    return ClientToServerMsgType(int(request_type)), message_data


# updating function is to send a message to the all clients that online from the server
def notify_new_client(new_client_nickname: str):
    connected_message = ServerToClientMsg("server", ServerToClientMsgType.CONNECTED, new_client_nickname)
    for nickname, client in CLIENTS_DICT.items():
        if nickname != new_client_nickname:
            send_message(nickname, connected_message)


def handle_connection(client, nickname: str):
    while True:
        try:
            # As long as we see a message from the client' we send it to all the clients in the chat
            request_type, message_data = recv_message(client)
            if request_type == ClientToServerMsgType.CONNECT:
                print(f"[+] Client: {nickname} reconnected")
            elif request_type == ClientToServerMsgType.DISCONNECT:
                print(f"[+] Client: {nickname} sent disconnection request, disconnecting")
                remove_and_disconnect_from_client(client, nickname)
                break
            elif request_type == ClientToServerMsgType.MESSAGE_USER:
                msg_data_lst = message_data.split(';;')
                recipient_nickname = msg_data_lst[0]
                msg_content = msg_data_lst[1]
                add_msg_to_db(nickname, recipient_nickname, msg_content)
                msg = ServerToClientMsg(sender_nickname=nickname,
                                        message_type=ServerToClientMsgType.MESSAGE_USER,
                                        message_data=msg_content)
                send_message(target_nickname=recipient_nickname, message=msg)
            elif request_type == ClientToServerMsgType.MESSAGE_ALL:
                msg = ServerToClientMsg(sender_nickname=nickname,
                                        message_type=ServerToClientMsgType.MESSAGE_USER,
                                        message_data=message_data)
                for client_nickname in CLIENTS_DICT.keys():
                    if client_nickname == nickname:
                        # Do not send msg back to the sender, we skip him
                        continue
                    add_msg_to_db(nickname, client_nickname, message_data)
                    send_message(target_nickname=client_nickname, message=msg)
            elif request_type == ClientToServerMsgType.GET_ALL_CLIENTS:
                all_clients = CLIENTS_DICT.keys()
                msg = ServerToClientMsg(sender_nickname=SERVER_NICKNAME,
                                        message_type=ServerToClientMsgType.REPLAY_ALL_CLIENTS,
                                        message_data="%".join(all_clients))
                send_message(target_nickname=nickname, message=msg)
            elif request_type == ClientToServerMsgType.GET_ALL_FILES:
                msg = ServerToClientMsg(sender_nickname=SERVER_NICKNAME,
                                        message_type=ServerToClientMsgType.REPLAY_ALL_FILES,
                                        message_data=get_server_folder_content())
                send_message(target_nickname=nickname, message=msg)
            elif request_type == ClientToServerMsgType.DOWNLOAD_FILE:
                thread = threading.Thread(target=send_file_rdt, args=(message_data, nickname, client))
                thread.start()
                thread_list.append(thread)
            elif request_type == ClientToServerMsgType.GET_ALL_MESSAGES:
                if nickname in USER_MSGS_DB.keys():
                    msg = ServerToClientMsg(sender_nickname=SERVER_NICKNAME,
                                            message_type=ServerToClientMsgType.REPLAY_ALL_MESSAGES,
                                            message_data="<>".join(USER_MSGS_DB[nickname]))
                    send_message(target_nickname=nickname, message=msg)
                else:
                    msg = ServerToClientMsg(sender_nickname=SERVER_NICKNAME,
                                            message_type=ServerToClientMsgType.REPLAY_ALL_MESSAGES,
                                            message_data="You have no messages on the server :( ")
                    send_message(target_nickname=nickname, message=msg)
            else:
                print("[-] Unknown Error!")
        except Exception as err:
            print(err)
            print('[-] Error: ' + str(err))
            remove_and_disconnect_from_client(client, nickname)
            break


# This function accepting all of the connections
def server_main():
    server = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server.bind((BIND_IP, SERVER_TCP_BIND_PORT))
    server.listen(MAX_CONNECTIONS)
    print('[+] Server is listening...')
    while True:
        client, address = server.accept()  # wait for eny connection to come
        print(f'[+] Connected to address {str(address)}')
        nick = client.recv(1024).decode()
        if nick in CLIENTS_DICT.keys():
            client.send(b"Name already exists, good bye!")
            continue
        connected_msg = ServerToClientMsg(sender_nickname=SERVER_NICKNAME,
                                          message_type=ServerToClientMsgType.CONNECTED,
                                          message_data="Successfully connected!")
        CLIENTS_DICT[nick] = client
        send_message(nick, connected_msg)
        print(f'[+] Client: {nick} was connected to the server successfully')
        notify_new_client(f'Client: {nick} has joined the chat')
        thread = threading.Thread(target=handle_connection, args=(client, nick))
        thread.start()
        thread_list.append(thread)


if __name__ == '__main__':
    server_main()
