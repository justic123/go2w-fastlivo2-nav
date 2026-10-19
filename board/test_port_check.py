import socket,unittest
from port_check import check_ports
class PortChecks(unittest.TestCase):
 def test_active_listener_rejected_even_with_reuse(self):
  with socket.socket() as s:
   s.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);s.bind(('127.0.0.1',0));s.listen(1)
   with self.assertRaisesRegex(RuntimeError,'仍被占用'):check_ports([s.getsockname()[1]])
 def test_closed_connection_allows_immediate_restart(self):
  with socket.socket() as server:
   server.setsockopt(socket.SOL_SOCKET,socket.SO_REUSEADDR,1);server.bind(('127.0.0.1',0));server.listen(1);port=server.getsockname()[1]
   with socket.create_connection(('127.0.0.1',port)) as client:
    conn,_=server.accept();conn.shutdown(socket.SHUT_WR);conn.close();client.recv(1)
  check_ports([port])
if __name__=='__main__':unittest.main()
