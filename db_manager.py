import pymssql
import bcrypt


# 默认配置 (保留作为备用)
DEFAULT_SERVER = '127.0.0.1'
DEFAULT_PORT = 1433
DB_USER = 'sa'
DB_PASSWORD = '123456' # 记得填写真密码
DB_NAME = 'WarCommanderDB'

class DBManager:
    def __init__(self):
        self.conn = None
        # [新增] 动态连接参数
        self.current_server = DEFAULT_SERVER
        self.current_port = DEFAULT_PORT

    def set_host(self, host_string):
        """ 解析用户输入的地址，格式支持 'IP' 或 'IP:PORT' """
        host_string = host_string.strip()
        if ":" in host_string:
            try:
                parts = host_string.split(":")
                self.current_server = parts[0]
                self.current_port = int(parts[1])
            except:
                print("[DB] Invalid Port Format, using default")
                self.current_server = host_string.split(":")[0]
                self.current_port = 1433
        else:
            self.current_server = host_string
            self.current_port = 1433
        
        print(f"[DB] Target set to: {self.current_server}:{self.current_port}")

    def connect(self):
        try:
            self.conn = pymssql.connect(
                server=self.current_server, # 使用动态变量
                port=self.current_port,     # 使用动态变量
                user=DB_USER, 
                password=DB_PASSWORD, 
                database=DB_NAME,
                login_timeout=5 # 设置超时，防止卡死太久
            )
            return True
        except Exception as e:
            print(f"[DB] Connect Error Details: {e}")
            return False

    def close(self):
        if self.conn: self.conn.close()

    def register_user(self, username, password):
        if not self.conn and not self.connect(): return "DB Error"
        
        # 密码加密
        salt = bcrypt.gensalt()
        hashed = bcrypt.hashpw(password.encode('utf-8'), salt).decode('utf-8')
        
        try:
            with self.conn.cursor() as cursor:
                # 检查重名
                cursor.execute("SELECT UID FROM Players WHERE Username=%s", (username,))
                if cursor.fetchone():
                    return "Username Taken"
                
                # 插入
                cursor.execute(
                    "INSERT INTO Players (Username, PasswordHash) VALUES (%s, %s)", 
                    (username, hashed)
                )
                self.conn.commit()
                return "Success"
        except Exception as e:
            print(f"[DB] Register Error: {e}")
            return "Error"

    def login_user(self, username, password):
        if not self.conn and not self.connect(): return None
        
        try:
            with self.conn.cursor(as_dict=True) as cursor:
                cursor.execute("SELECT UID, Username, PasswordHash FROM Players WHERE Username=%s", (username,))
                row = cursor.fetchone()
                
                if row:
                    stored_hash = row['PasswordHash'].encode('utf-8')
                    if bcrypt.checkpw(password.encode('utf-8'), stored_hash):
                        return {"uid": row['UID'], "name": row['Username']}
        except Exception as e:
            print(f"[DB] Login Error: {e}")
            
        return None