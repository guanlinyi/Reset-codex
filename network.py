"""Discover a running local proxy without fixed ports or reading other apps' files."""
import ipaddress
import socket
import ssl
import threading
import time
import psutil

NAMES=('clash','mihomo','v2ray','xray','sing-box','sslocal','geph','hiddify','nekobox','naiveproxy')
_lock=threading.Lock()
_cached=''
_checked=0

def has_discovered_proxy():return bool(_cached)

def local_proxy():
    global _cached,_checked
    with _lock:
        if _checked and time.monotonic()-_checked<30:return _cached
        _checked=time.monotonic();_cached=''
        candidates=set()
        for proc in psutil.process_iter(['name']):
            if not any(name in (proc.info['name'] or '').lower() for name in NAMES):continue
            try:
                for connection in proc.net_connections(kind='tcp'):
                    if connection.status!=psutil.CONN_LISTEN or not connection.laddr:continue
                    host,port=connection.laddr[:2]
                    address=ipaddress.ip_address(host)
                    if address.is_loopback or address.is_unspecified:
                        candidates.add(('::1' if address.version==6 else '127.0.0.1',port))
            except (psutil.Error,OSError,ValueError):continue
        # Only listeners owned by known running proxy clients; no port-range scanning.
        for host,port in sorted(candidates)[:8]:
            try:
                with socket.create_connection((host,port),timeout=1.5) as stream:
                    stream.sendall(b'CONNECT auth.openai.com:443 HTTP/1.1\r\nHost: auth.openai.com:443\r\n\r\n')
                    header=b''
                    while b'\r\n\r\n' not in header and len(header)<4096:
                        chunk=stream.recv(1)
                        if not chunk:break
                        header+=chunk
                    if not header.startswith((b'HTTP/1.1 200 ',b'HTTP/1.0 200 ')):continue
                    # Verify the target's TLS certificate before using a discovered proxy.
                    # No login token, cookie, chat, or model request is sent by this check.
                    with ssl.create_default_context().wrap_socket(stream,server_hostname='auth.openai.com'):
                        _cached='http://'+('['+host+']' if ':' in host else host)+':'+str(port)
                        return _cached
            except (OSError,ssl.SSLError):continue
        return ''
