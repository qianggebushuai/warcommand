import socket
import threading
import json
import time

class NetworkManager:
    def __init__(self):
        self.role = None  # "HOST" 或 "CLIENT"
        self.running = True
        self.lock = threading.Lock()
        
        # 消息队列
        self.received_queue = [] 
        
        # --- Host 属性 ---
        self.server_socket = None
        self.clients = {} # {addr_str: conn} 
        self.client_data = {} # {addr_str: info}
        
        # --- Client 属性 ---
        self.client_socket = None
        self.connected = False
        
        # [确保存在]
        self.allow_join = True 

    # ================== HOST ==================
    def start_host(self, port=9999):
        # 先清理旧的
        self.stop_hosting()
        
        try:
            self.role = "HOST"
            self.running = True
            self.allow_join = True
            
            self.server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.server_socket.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
            self.server_socket.bind(('0.0.0.0', port))
            self.server_socket.listen(5)
            print(f"[NET] Host started on port {port}")
            
            self.accept_thread = threading.Thread(target=self.accept_loop, daemon=True)
            self.accept_thread.start()
            
            self.connected = True
            return True
        except Exception as e:
            print(f"[NET] Host Start Error: {e}")
            self.stop_hosting() # 启动失败也要清理
            return False

    def accept_loop(self):
        while self.running:
            try:
                # 设置超时，让循环有机会检查 self.running
                self.server_socket.settimeout(1.0) 
                conn, addr = self.server_socket.accept()
                
                # 恢复阻塞模式给子线程用
                conn.settimeout(None) 
                
                if not self.allow_join:
                    print(f"[NET] Rejected {addr} (Game in progress)")
                    conn.close()
                    continue
                    
                addr_str = f"{addr[0]}:{addr[1]}"
                print(f"[NET] New connection: {addr_str}")
                
                with self.lock:
                    self.clients[addr_str] = conn
                    self.client_data[addr_str] = {"name": "Unknown", "ready": False}
                
                threading.Thread(target=self.handle_client, args=(conn, addr_str), daemon=True).start()
                
                self.send_to(addr_str, {"type": "WELCOME", "id": addr_str})
                
            except socket.timeout:
                continue # 超时了，检查 running，继续循环
            except OSError: 
                # Socket 被关闭了
                break
            except Exception as e: 
                print(f"Accept error: {e}")
                break

    def handle_client(self, conn, addr_str):
        buffer = ""
        while self.running:
            try:
                data = conn.recv(4096).decode('utf-8')
                if not data: break
                
                buffer += data
                while "\n" in buffer:
                    message, buffer = buffer.split("\n", 1)
                    if message.strip():
                        with self.lock:
                            try:
                                parsed = json.loads(message)
                                parsed['_sender'] = addr_str
                                self.received_queue.append(parsed)
                                
                                # [转发 CHAT]
                                if parsed.get('type') == 'CHAT':
                                    self.broadcast(parsed, exclude_id=addr_str)
                            except: pass
            except: break
        
        print(f"[NET] Client {addr_str} disconnected")
        self.disconnect_client(addr_str) # 封装清理逻辑

    def disconnect_client(self, addr_str):
        with self.lock:
            if addr_str in self.clients:
                try: self.clients[addr_str].close()
                except: pass
                del self.clients[addr_str]
            if addr_str in self.client_data: 
                del self.client_data[addr_str]
        
        self.received_queue.append({"type": "PLAYER_LEFT", "id": addr_str})

    def send_to(self, target_id, data):
        with self.lock: # 加锁防止多线程冲突
            if target_id in self.clients:
                try:
                    msg = json.dumps(data) + "\n"
                    self.clients[target_id].sendall(msg.encode('utf-8'))
                except: 
                    print(f"[NET] Send error to {target_id}")
                    # 这里不要急着删，让 handle_client 去处理断开

    def broadcast(self, data, exclude_id=None):
        msg = json.dumps(data) + "\n"
        encoded = msg.encode('utf-8')
        with self.lock:
            # 使用 list() 复制 keys，防止遍历时字典被修改
            for cid in list(self.clients.keys()):
                if cid != exclude_id:
                    try: 
                        self.clients[cid].sendall(encoded)
                    except: pass

    # ================== CLIENT ==================
    def connect(self, ip, port=9999):
        self.stop_hosting() # 清理旧状态
        try:
            self.role = "CLIENT"
            self.client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
            self.client_socket.settimeout(5)
            self.client_socket.connect((ip, port))
            self.client_socket.settimeout(None)
            self.connected = True
            self.running = True # 确保 running 为 True
            
            threading.Thread(target=self.client_receive_loop, daemon=True).start()
            return True
        except Exception as e:
            print(f"[NET] Connect Error: {e}")
            return False

    def client_receive_loop(self):
        buffer = ""
        while self.running and self.connected:
            try:
                data = self.client_socket.recv(4096).decode('utf-8')
                if not data: break
                
                buffer += data
                while "\n" in buffer:
                    message, buffer = buffer.split("\n", 1)
                    if message.strip():
                        with self.lock:
                            try:
                                parsed = json.loads(message)
                                self.received_queue.append(parsed)
                            except: pass
            except: break
        
        self.connected = False
        print("[NET] Disconnected from server")

    # ================== COMMON ==================
    def send(self, data):
        msg = json.dumps(data) + "\n"
        encoded = msg.encode('utf-8')
        
        if self.role == "CLIENT":
            if self.connected and self.client_socket:
                try: self.client_socket.sendall(encoded)
                except: self.connected = False
        
        elif self.role == "HOST":
            self.broadcast(data)

    def stop_hosting(self):
        """ 彻底关闭网络功能，清理所有资源 """
        self.connected = False
        self.running = False
        
        # 1. 关闭 Server Socket
        if self.server_socket:
            try:
                # 强制关闭，让 accept_loop 抛出 OSError 并退出
                self.server_socket.close() 
            except: pass
            self.server_socket = None
            
        # 2. 关闭 Client Socket
        if self.client_socket:
            try: self.client_socket.close()
            except: pass
            self.client_socket = None
            
        # 3. 关闭所有连接的 Clients
        with self.lock:
            for conn in self.clients.values():
                try: conn.close()
                except: pass
            self.clients.clear()
            self.client_data.clear()
            
        print("[NET] Network stopped")

    def get_messages(self):
        with self.lock:
            msgs = self.received_queue[:]
            self.received_queue.clear()
            return msgs
            
    def get_client_count(self):
        if self.role == "HOST":
            with self.lock:
                return len(self.clients)
        return 0