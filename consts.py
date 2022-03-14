import enum
import hashlib

BIND_IP = '0.0.0.0'
SERVER_IP = "127.0.0.1"
SERVER_TCP_BIND_PORT = 55000
PORTS_RANGE = 15
MAX_CONNECTIONS = 5
SERVER_NICKNAME = "SERVER"
UDP_MAX_DATAGRAM_SIZE = 1024
MAX_FILE_SIZE = 9 * UDP_MAX_DATAGRAM_SIZE
MAX_DATA_SIZE = UDP_MAX_DATAGRAM_SIZE - 5 # max udp packet minus sequence number and checksum sizes


def calculate_checksum(data):
    return hashlib.sha1(data).hexdigest()[-4:]


class ClientToServerMsgType(enum.Enum):  # Client -> Server
    CONNECT = 1
    DISCONNECT = 2
    MESSAGE_USER = 3
    MESSAGE_ALL = 4
    GET_ALL_CLIENTS = 5
    GET_ALL_FILES = 6
    DOWNLOAD_FILE = 7
    GET_ALL_MESSAGES = 8
    MAX_VALUE = 9


class ClientToServerMsg:
    """
    Client -> Server
    |<ClientToServerMsgType>~<MessageData>|
    """

    def __init__(self, msg_type: ClientToServerMsgType, message_data: str = ""):
        self.msg_type = msg_type
        self.message_data = message_data

    def to_string(self):
        return f"|{str(self.msg_type.value)}~{str(self.message_data)}|"


class ServerToClientMsgType(enum.Enum):  # Server -> Client
    CONNECTED = 1
    DISCONNECTED = 2
    MESSAGE_USER = 3
    REPLAY_ALL_CLIENTS = 4
    REPLAY_ALL_FILES = 5
    DOWNLOAD_FILE = 6
    REPLAY_ALL_MESSAGES = 7
    MAX_VALUE = 8


class ServerToClientMsg:
    """
    Server -> Client
    |<ServerToClientMsgType>~<SenderNickName>~<MessageData>|

    SenderNickName can be either SERVER_NAME or real client sender nickname
    """

    def __init__(self, sender_nickname: str, message_type: ServerToClientMsgType, message_data: str = ""):
        self.sender_nickname = sender_nickname
        self.message_type_num = message_type.value
        self.message_data = message_data

    def to_string(self):
        return f"|{self.message_type_num}~{self.sender_nickname}~{self.message_data}|"