include .env
export

clean:
	sudo rm -rf .venv
	sudo rm -rf rpi-rgb-led-matrix

create:
	virtualenv -p 3.11 .venv
	$(MAKE) install-all

disable:
	sudo systemctl disable smart_mini_crt_interface.service

enable:
	sudo systemctl enable smart_mini_crt_interface.service

install-python:
	.venv/bin/pip install -r requirements.txt

install-service:
	sudo cp service/smart_mini_crt_interface.service /etc/systemd/system/
	sudo systemctl daemon-reload

install-all:
	@$(MAKE) install-python
	@$(MAKE) install-service

rain:
	sudo .venv/bin/python smart_mini_crt_interface/rain.py

restart:
	sudo systemctl restart smart_mini_crt_interface.service

run:
	.venv/bin/python smart_mini_crt_interface/main.py

start:
	sudo systemctl start smart_mini_crt_interface.service

stop:
	sudo systemctl stop smart_mini_crt_interface.service

tail:
	clear && sudo journalctl -u smart_mini_crt_interface.service -f -n 50

update:
	git add .
	git stash save "Stash before update @ $(shell date)"
	git pull --prune
	@$(MAKE) install-all

vscode-shortcut-1:
	poetry run python smart_mini_crt_interface/main.py
