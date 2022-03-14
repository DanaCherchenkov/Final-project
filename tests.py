from consts import ClientToServerMsg, ClientToServerMsgType, ServerToClientMsgType, ServerToClientMsg
import server
import unittest

server.get_server_folder_content()


class test_msg_protocol(unittest.TestCase):
    # test the message from the client to the server
    def test_client_to_server_msg(self):
        msg = ClientToServerMsg(msg_type=ClientToServerMsgType.MESSAGE_ALL,
                                message_data="Hello World!")
        assert msg.to_string() == '|4~Hello World!|'
        msg = ClientToServerMsg(msg_type=ClientToServerMsgType.CONNECT,
                                message_data="")
        assert msg.to_string() == '|1~|'

    # test the message from the server to the client
    def test_server_to_client_msg(self):
        """
        |<ServerToClientMsgType>~<SenderNickName>~<MessageData>|
        f"|{str(message.message_type_num)}~{str(message.sender_nickname)}~{str(message.message_data)}|"
        """
        msg = ServerToClientMsg(sender_nickname="Dana",
                                message_type=ServerToClientMsgType.DISCONNECTED,
                                message_data="Gal")
        assert f"|{ServerToClientMsgType.DISCONNECTED.value}~Dana~Gal|" == msg.to_string()


class test_packet_corruption(unittest.TestCase):
    # test the server files folder
    def test_server_files(self):
        files_str = server.get_server_folder_content()
        all_files = files_str.split("#")
        assert len(all_files) == 4
        assert len(all_files) != 3
        assert len(all_files) != 5
        assert "3egg.jpg" in all_files
        assert "3egjpg" not in all_files

    # test the 'corrupt_packet' function
    def test_packet_corruptor(self):
        for file in server.get_server_folder_content().split("#"):
            with open(server.get_file_path_by_name(file), "rb") as f:
                data = f.read()
                corrupted_data = server.corrupt_packet(data)
                assert data != corrupted_data


if __name__ == '__main__':
    unittest.main()
    test_msg_protocol()
