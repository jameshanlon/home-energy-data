OUTPUT_DIR=output

all: install run build

install: venv
	. venv/bin/activate && ( \
			pip install -r requirements.txt; \
			pre-commit install; \
		)
	cd frontend && npm install

venv:
	test -d venv || python3 -m venv venv

run:
	. venv/bin/activate && ( \
		./analyse-energy-data.py --output-dir ${OUTPUT_DIR} \
	)

build:
	bash -c 'source $$HOME/.nvm/nvm.sh && nvm use 20 && cd frontend && npm run build'

serve:
	python3 -m http.server 8001 --directory ${OUTPUT_DIR}

test:
	. venv/bin/activate && pytest tests/ -v

clean:
	rm -rfv venv
	rm -rfv ${OUTPUT_DIR}
	rm -rfv frontend/node_modules
