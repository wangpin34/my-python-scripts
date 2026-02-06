.PHONY: install venv use_venv freeze dev
venv:
	python3 -m venv .venv
	. .venv/bin/activate

use_venv:
	. .venv/bin/activate

install: venv
	pip install -r requirements.txt

freeze:
	pip freeze > requirements.txt
