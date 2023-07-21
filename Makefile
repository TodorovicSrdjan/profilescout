SRC_DIR = profile_crawler/
TEST_DIR = tests/

.PHONY: init test

init:
	pip install -r requirements.txt

test:
	pytest $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=term-missing

lint:
	flake8 $(SRC_DIR) --max-line-length 140

build:
	python setup.py

clean:
	rm -rf profile_crawler/downloads/*
	rm nohup.out
