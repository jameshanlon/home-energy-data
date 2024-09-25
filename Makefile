OUTPUT_DIR=output

all: install run

install: venv
	. venv/bin/activate && ( \
			pip install -r requirements.txt; \
			pre-commit install; \
		)

venv:
	test -d venv || python3 -m venv venv

run:
	. venv/bin/activate && ( \
		./analyse-energy-data.py --output-dir ${OUTPUT_DIR} \
	)

serve:
	. venv/bin/activate && python -m http.server -p 10002 -d ${OUTPUT_DIR}

clean:
	rm -rfv venv
	rm -rfv ${OUTPUT_DIR}
