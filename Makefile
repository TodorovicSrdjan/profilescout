SRC_DIR = src/
TEST_DIR = tests/

.PHONY: init test

init:
	pip install -r requirements.txt

test:
	pytest $(TEST_DIR) --cov=$(SRC_DIR) --cov-report=term-missing

lint:
	flake8 $(SRC_DIR) --max-line-length 140

clean:
	rm -rf ./downloads/* 2>/dev/null
	rm nohup.out 2>/dev/null
