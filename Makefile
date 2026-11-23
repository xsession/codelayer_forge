.PHONY: doctor catalog test verify demo web plugin-packages package rust-test engine-setup engine-test lab

doctor:
	python3 scripts/doctor.py

catalog:
	python3 scripts/build_catalog.py

test:
	python3 -m unittest discover -s tests -v

verify: catalog test
	python3 scripts/verify_repo.py
	node --check apps/desktop/web/app.js

demo:
	python3 scripts/demo.py

web:
	python3 -m http.server 4173 --directory apps/desktop/web

plugin-packages:
	mkdir -p dist/plugins
	for plugin in plugins/*; do if [ -f "$$plugin/plugin.toml" ]; then python3 scripts/pack_plugin.py "$$plugin" --output dist/plugins; fi; done

package: verify plugin-packages
	python3 scripts/package_release.py

rust-test:
	cargo test --workspace

ENGINE := engines/embeddyn

engine-setup:
	cd $(ENGINE) && python3 -m pip install -e . pytest pytest-asyncio httpx

engine-test:
	cd $(ENGINE) && python3 -m pytest -q tests/mechatronics

lab:
	cd $(ENGINE) && python3 -m embeddyn mechatronics gui examples/mechatronics/rc-servo-lab.yaml --open
