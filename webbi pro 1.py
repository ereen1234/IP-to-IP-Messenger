import socket
import threading
import tkinter as tk
from tkinter import messagebox, ttk
import time
from datetime import datetime
import sqlite3
from cryptography.fernet import Fernet

class RobustChat:
    def __init__(self, root):
        self.root = root
        self.root.title("webbi")
        self.root.geometry("400x650")
        self.root.configure(bg="#121212")

        self.client = None
        self.nickname = ""
        self.is_connected = False
        self.is_admin = False
        self.server_clients = {}
        self.banned_ips = {}
        self.admin_win = None
        self.cipher = None
        self.server_key = None

        self.db_conn = sqlite3.connect("secure_chat.db", check_same_thread=False)
        self.cursor = self.db_conn.cursor()
        self.cursor.execute('CREATE TABLE IF NOT EXISTS messages (sender TEXT, msg TEXT, time TEXT)')
        self.db_conn.commit()

        self.setup_login_ui()

    def encrypt(self, text: str) -> str:
        if self.cipher is None: return text
        return self.cipher.encrypt(text.encode('utf-8')).decode('utf-8')

    def decrypt(self, text: str) -> str:
        if self.cipher is None: return text
        try: return self.cipher.decrypt(text.encode('utf-8')).decode('utf-8')
        except: return "[Mesaj Çözülemedi]"

    def setup_login_ui(self):
        self.login_frame = tk.Frame(self.root, bg="#121212")
        self.login_frame.place(relx=0.5, rely=0.5, anchor="center")
        tk.Label(self.login_frame, text="WEBBİ", fg="#25D366", bg="#121212", font=("Arial", 24, "bold")).pack(pady=20)
        self.name_ent = tk.Entry(self.login_frame, font=("Arial", 12))
        self.name_ent.pack(pady=10)
        self.ip_ent = tk.Entry(self.login_frame, font=("Arial", 12))
        self.ip_ent.insert(0, socket.gethostbyname(socket.gethostname()))
        self.ip_ent.pack(pady=5)
        tk.Button(self.login_frame, text="SUNUCU KUR VE YÖNET", bg="#075E54", fg="white", width=25, command=self.host_and_join).pack(pady=10)
        tk.Button(self.login_frame, text="SADECE KATIL", bg="#25D366", fg="black", width=25, command=self.join_only).pack()

    def host_and_join(self):
        self.is_admin = True
        threading.Thread(target=self.run_server, daemon=True).start()
        time.sleep(0.4)
        self.join_only()

    def run_server(self):
        self.server_key = Fernet.generate_key()
        self.cipher = Fernet(self.server_key)
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        s.setsockopt(socket.SOL_SOCKET, socket.SO_REUSEADDR, 1)
        try:
            s.bind(('0.0.0.0', 55555))
            s.listen()
            while True:
                conn, addr = s.accept()
                threading.Thread(target=self.server_relay, args=(conn, addr), daemon=True).start()
        except: pass

    def server_relay(self, conn, addr):
        try:
            conn.send(self.server_key)
            nick_data = conn.recv(1024)
            if not nick_data: return
            nickname = self.cipher.decrypt(nick_data).decode('utf-8')
            self.server_clients[conn] = (nickname, addr[0])
            self.broadcast_sys(f"{nickname} odaya katıldı!")
            self.root.after(0, self.update_admin_ui)
            while True:
                data = conn.recv(4096)
                if not data: break
                if addr[0] in self.banned_ips:
                    conn.send(self.cipher.encrypt("SYS_NOTIF:Susturulduğunuz için mesajınız gönderilemedi!".encode('utf-8')))
                    continue
                self.cursor.execute("INSERT INTO messages VALUES (?, ?, ?)", (nickname, data.decode('utf-8'), datetime.now().strftime("%H:%M")))
                self.db_conn.commit()
                self.broadcast_chat(nickname, data.decode('utf-8'))
        except:
            if conn in self.server_clients: del self.server_clients[conn]
            self.root.after(0, self.update_admin_ui)
            conn.close()

    def broadcast_sys(self, msg: str):
        packet = self.cipher.encrypt(f"SYS_NOTIF:{msg}".encode('utf-8'))
        for c in list(self.server_clients.keys()):
            try: c.send(packet)
            except: pass

    def broadcast_chat(self, nickname: str, enc_content: str):
        packet = self.cipher.encrypt(f"{nickname}|{enc_content}".encode('utf-8'))
        for c in list(self.server_clients.keys()):
            try: c.send(packet)
            except: pass

    def open_admin_panel(self):
        if self.admin_win and self.admin_win.winfo_exists():
            self.admin_win.lift(); return
        self.admin_win = tk.Toplevel(self.root)
        self.admin_win.title("Yönetim Paneli")
        self.admin_win.geometry("350x550")
        self.admin_win.configure(bg="#1e1e1e")
        
        tk.Label(self.admin_win, text="AKTİF KULLANICILAR", fg="#25D366", bg="#1e1e1e", font=("Arial", 9, "bold")).pack(pady=5)
        self.user_list = ttk.Treeview(self.admin_win, columns=("Name", "IP"), show='headings', height=6)
        self.user_list.heading("Name", text="İsim"); self.user_list.heading("IP", text="IP Adresi")
        self.user_list.column("Name", width=120); self.user_list.column("IP", width=120)
        self.user_list.pack(padx=10, pady=5)
        
        tk.Button(self.admin_win, text="SEÇİLENİ SUSTUR (BAN)", bg="#cc0000", fg="white", command=self.ban_selected).pack(fill="x", padx=20, pady=5)
        
        tk.Label(self.admin_win, text="SUSTURULANLAR LİSTESİ", fg="#ff4444", bg="#1e1e1e", font=("Arial", 9, "bold")).pack(pady=5)
        self.ban_tree = ttk.Treeview(self.admin_win, columns=("Name", "IP"), show='headings', height=6)
        self.ban_tree.heading("Name", text="İsim"); self.ban_tree.heading("IP", text="Banlı IP")
        self.ban_tree.pack(padx=10, pady=5)
        
        tk.Button(self.admin_win, text="SUSTURMAYI KALDIR", bg="#00a884", fg="white", command=self.unban_selected).pack(fill="x", padx=20, pady=5)
        tk.Button(self.admin_win, text="GENEL DUYURU YAP", bg="#34B7F1", fg="black", command=self.send_announcement).pack(fill="x", padx=20, pady=10)
        self.update_admin_ui()

    def update_admin_ui(self):
        if hasattr(self, 'user_list') and self.admin_win and self.admin_win.winfo_exists():
            for i in self.user_list.get_children(): self.user_list.delete(i)
            for conn, info in list(self.server_clients.items()):
                self.user_list.insert("", "end", values=(info[0], info[1]))
            for i in self.ban_tree.get_children(): self.ban_tree.delete(i)
            for ip, name in self.banned_ips.items():
                self.ban_tree.insert("", "end", values=(name, ip))

    def ban_selected(self):
        selected = self.user_list.selection()
        if not selected: return
        name, ip = self.user_list.item(selected[0])['values']
        if name == self.nickname:
            messagebox.showwarning("Hata", "Kendi kendinizi susturamazsınız!")
            return
        if messagebox.askyesno("Onay", f"{name} kullanıcısı susturulsun mu?"):
            self.banned_ips[ip] = name
            self.broadcast_sys(f"{name} yönetici tarafından susturuldu.")
            self.update_admin_ui()

    def unban_selected(self):
        selected = self.ban_tree.selection()
        if selected:
            name, ip = self.ban_tree.item(selected[0])['values']
            if ip in self.banned_ips:
                del self.banned_ips[ip]
                messagebox.showinfo("Başarılı", "Kullanıcının susturması kaldırıldı.")
                self.update_admin_ui()

    def send_announcement(self):
        pop = tk.Toplevel(self.admin_win)
        pop.title("Duyuru")
        entry = tk.Entry(pop, width=40); entry.pack(padx=20, pady=10)
        tk.Button(pop, text="Yayınla", command=lambda: [self.broadcast_sys(f"[DUYURU] {entry.get()}"), pop.destroy()]).pack(pady=5)

    def join_only(self):
        self.nickname = self.name_ent.get().strip()
        if not self.nickname: return
        target_ip = self.ip_ent.get().strip()
        threading.Thread(target=self._connect_task, args=(target_ip,), daemon=True).start()

    def _connect_task(self, target_ip):
        self.client = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        try:
            self.client.connect((target_ip, 55555))
            key = self.client.recv(44)
            self.cipher = Fernet(key)
            self.client.send(self.cipher.encrypt(self.nickname.encode('utf-8')))
            self.is_connected = True
            self.root.after(0, self.show_chat_ui)
            threading.Thread(target=self.receive_messages, daemon=True).start()
        except: self.root.after(0, lambda: messagebox.showerror("Hata", "Bağlantı kurulamadı!"))

    def show_chat_ui(self):
        self.login_frame.destroy()
        if self.is_admin:
            tk.Button(self.root, text="YÖNETİM PANELİ", bg="#075E54", fg="white", font=("Arial", 10, "bold"), command=self.open_admin_panel).pack(side="top", fill="x")
        chat_frame = tk.Frame(self.root, bg="#0d1418")
        chat_frame.pack(padx=5, pady=5, fill='both', expand=True)
        self.canvas = tk.Canvas(chat_frame, bg="#0d1418", highlightthickness=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.msg_container = tk.Frame(self.canvas, bg="#0d1418")
        self.canvas.create_window((0, 0), window=self.msg_container, anchor="nw", width=360)
        self.msg_container.bind("<Configure>", lambda e: self.canvas.configure(scrollregion=self.canvas.bbox("all")))
        input_frame = tk.Frame(self.root, bg="#121212")
        input_frame.pack(fill='x', side='bottom', padx=10, pady=10)
        self.msg_ent = tk.Entry(input_frame, bg="#2a3942", fg="white", font=("Arial", 12))
        self.msg_ent.pack(side='left', fill='x', expand=True, ipady=8)
        self.msg_ent.bind("<Return>", lambda e: self.send_message())
        tk.Button(input_frame, text="GÖNDER", command=self.send_message, bg="#00a884", fg="white").pack(side='right', padx=5)

    def receive_messages(self):
        while self.is_connected:
            try:
                raw = self.client.recv(4096)
                if not raw: break
                dec = self.cipher.decrypt(raw).decode('utf-8')
                if "|" in dec:
                    s, c = dec.split("|", 1)
                    if s != self.nickname: self.root.after(0, self.add_bubble, f"{s}: {self.decrypt(c)}")
                elif "SYS_NOTIF:" in dec:
                    self.root.after(0, self.add_system_label, dec.replace("SYS_NOTIF:", ""))
            except: break

    def send_message(self):
        msg = self.msg_ent.get().strip()
        if msg:
            try:
                self.client.send(self.encrypt(msg).encode('utf-8'))
                self.add_bubble(f"{self.nickname}: {msg}")
                self.msg_ent.delete(0, 'end')
            except: pass

    # ================== ESKİ TASARIM MESAJ BALONLARI ==================
    def add_system_label(self, text):
        row = tk.Frame(self.msg_container, bg="#0d1418")
        row.pack(fill="x", pady=5)
        tk.Label(row, text=text, fg="#8696a0", bg="#0d1418", font=("Arial", 8, "italic")).pack()
        self.canvas.yview_moveto(1.0)

    def add_bubble(self, msg, time_str=None):
        z = time_str if time_str else datetime.now().strftime("%H:%M")
        row = tk.Frame(self.msg_container, bg="#0d1418")
        row.pack(fill="x", pady=2)
        is_me = msg.startswith(f"{self.nickname}:")
        color = "#005c4b" if is_me else "#202c33"
        bubble = tk.Frame(row, bg=color, padx=10, pady=5)
        bubble.pack(side="right" if is_me else "left", padx=10)
        tk.Label(bubble, text=msg, bg=color, fg="white", font=("Arial", 10), wraplength=250).pack()
        tk.Label(bubble, text=z, bg=color, fg="#8696a0", font=("Arial", 7)).pack(anchor="e")
        self.canvas.yview_moveto(1.0)

if __name__ == "__main__":
    root = tk.Tk(); app = RobustChat(root); root.mainloop()
