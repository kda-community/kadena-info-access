
INIT=-D__INIT__

YAML_FILES := $(shell seq -f '"tx-%g.yaml"' 0 19)
JSON_FILES := $(shell seq -f '"tx-%g.json"' 0 19)

all: $(YAML_FILES)

.kia.pact: kia.pact.m4 ../pact/kia.pact
	m4 -I../pact -D__NS__=n_40c883decc192e1e3214898f04656b2e9ea7b74e ${INIT} $< > $@

.yaml.stamp: .kia.pact kia_deploy.tkpl config.yaml
	kda gen -t kia_deploy.tkpl -d config.yaml
	touch $@


$(YAML_FILES): .yaml.stamp

clean:
	rm -f .yaml.stamp $(YAML_FILES) $(JSON_FILES) .kia.pact
