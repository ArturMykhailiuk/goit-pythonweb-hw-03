from http.server import BaseHTTPRequestHandler
from collections import defaultdict
import socket
import urllib.parse
import mimetypes
import pathlib
import datetime
import multiprocessing
import socketserver
import json
import os
from jinja2 import Environment, FileSystemLoader


class HttpHandler(BaseHTTPRequestHandler):
    def do_GET(self):
        pr_url = urllib.parse.urlparse(self.path)
        if pr_url.path == "/":
            self.send_html_file("index.html")
        elif pr_url.path == "/message":
            self.send_html_file("message.html")
        elif pr_url.path == "/read":
            print("Handling /read request")

            self.send_html_file("read.html")

        else:
            if pathlib.Path().joinpath(pr_url.path[1:]).exists():
                self.send_static()
            else:
                self.send_html_file("error.html", 404)

    def send_html_file(self, filename, status=200):
        self.send_response(status)
        self.send_header("Content-type", "text/html")
        self.end_headers()
        with open(filename, "rb") as fd:
            self.wfile.write(fd.read())

    def send_static(self):
        self.send_response(200)
        mt = mimetypes.guess_type(self.path)
        if mt:
            self.send_header("Content-type", mt[0])
        else:
            self.send_header("Content-type", "text/plain")
        self.end_headers()
        with open(f".{self.path}", "rb") as file:
            self.wfile.write(file.read())

    def do_POST(self):
        data = self.rfile.read(int(self.headers["Content-Length"]))

        client_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        client_socket.connect(("localhost", 5000))
        client_socket.sendall(data)
        print("Дані надіслано")
        client_socket.close()

        self.send_response(302)
        self.send_header("Location", "/message.html")
        self.end_headers()


def run_http():
    http = socketserver.TCPServer(("", 3000), HttpHandler)
    try:
        print("HTTP-сервер стартував і очікує на підключення...")
        http.serve_forever()
    except KeyboardInterrupt:
        http.server_close()


def run_socket():
    server_socket = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
    server_socket.bind(("localhost", 5000))
    server_socket.listen(1)
    print("Socket-сервер стартував і очікує на підключення...")

    while True:
        client_socket, addr = server_socket.accept()
        print(f"Підключення від Socket-клієнта {addr}")

        try:
            # Отримання даних форми
            data = client_socket.recv(1024).decode()
            data_parse = urllib.parse.unquote_plus(data)
            data_dict = {
                "date": datetime.datetime.now().strftime("%Y-%m-%d %H:%M:%S.%f")
            }
            data_dict.update(
                {
                    key: value
                    for key, value in [el.split("=") for el in data_parse.split("&")]
                }
            )
            print(f"Дані отримано: {data_dict}")
            save_to_json(data_dict)
            read_messages()
        except KeyboardInterrupt:
            client_socket.close()


def save_to_json(data_dict):
    file_path = "./storage/data.json"
    os.makedirs(os.path.dirname(file_path), exist_ok=True)

    if os.path.exists(file_path):
        with open(file_path, "r+", encoding="utf-8") as file:
            try:
                data = json.load(file)
                if not isinstance(data, list):
                    data = [data]
            except json.JSONDecodeError:
                data = []
            data.append(data_dict)
            file.seek(0)
            json.dump(data, file, ensure_ascii=False, indent=4)
    else:
        with open(file_path, "w", encoding="utf-8") as file:
            json.dump([data_dict], file, ensure_ascii=False, indent=4)
    print("Дані збережено в файлі data.json")


def group_messages_by_date(messages):
    grouped_messages = defaultdict(list)
    for message in messages:
        date = message.get("date", "Unknown Date")
        date = date.split(" ")[0]
        grouped_messages[date].append(message)
    return grouped_messages


def read_messages():
    messages = []
    with open("./storage/data.json", "r", encoding="utf-8") as file:
        try:
            messages = json.load(file)
            if not isinstance(messages, list):
                messages = [messages]
        except json.JSONDecodeError:
            messages = []

    grouped_messages = group_messages_by_date(messages)

    env = Environment(loader=FileSystemLoader("."))
    template = env.get_template("./templates/read.html")
    output = template.render(grouped_messages=grouped_messages)

    with open("./read.html", "w", encoding="utf-8") as fh:
        fh.write(output)

    print("read.html has been updated")


if __name__ == "__main__":

    read_messages()

    # Запуск процесу для HTTP-серверу
    http_process = multiprocessing.Process(target=run_http)
    http_process.start()

    # Запуск процесу для Socket-серверу
    socket_process = multiprocessing.Process(target=run_socket)
    socket_process.start()

    try:
        # Очікування завершення процесів
        http_process.join()
        socket_process.join()
    except KeyboardInterrupt:
        http_process.terminate()
        socket_process.terminate()
        print("HTTP та Socket процеси завершено після натискання Ctrl+C.")
